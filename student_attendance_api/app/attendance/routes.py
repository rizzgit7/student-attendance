"""Student check-in (blueprint §10/§13).

POST /attendance/check-in  – validate code + session, mark PRESENT/LATE
GET  /attendance/today     – today's records
GET  /attendance/history   – paginated history
GET  /attendance/summary   – subject-wise attendance + percentage (§8)
"""
from flask import Blueprint, g, jsonify, request

from app.extensions import db
from app.models import (
    AttendanceRecord, AttendanceSession, MarkStatus, Student, as_utc, utcnow,
)
from app.utils import api_error, rate_limit_guard, require_role
from app.utils.timing import CheckinError, classify, session_open

bp = Blueprint("attendance", __name__)


def _get_student(user):
    student = Student.query.filter_by(user_id=user.id).first()
    if student is None:
        return None
    return student


def _record_json(record):
    session = record.session
    return {
        "id": record.id,
        "session_id": record.session_id,
        "subject": session.subject.name if session.subject else None,
        "subject_id": session.subject_id,
        "section": session.section.name if session.section else None,
        "scheduled_start_at": session.scheduled_start_at.isoformat(),
        "status": record.status,
        "recorded_at": record.recorded_at.isoformat(),
        "is_corrected": bool(record.is_corrected),
    }


@bp.post("/attendance/check-in")
@require_role("STUDENT")
@rate_limit_guard("checkin", "RATELIMIT_CHECKIN_PER_MINUTE")
def check_in():
    data = request.get_json(silent=True) or {}
    code = str(data.get("code") or "").strip()
    session_id = data.get("session_id")
    if not code:
        return api_error(400, "validation_error", "code is required")

    student = _get_student(g.user)
    if student is None:
        return api_error(403, "no_student_profile",
                         "Account has no student profile")

    # --- locate candidate session -----------------------------------------
    if session_id:
        session = AttendanceSession.query.filter_by(
            id=int(session_id), institution_id=student.institution_id
        ).first()
        if session is None:
            return api_error(404, "not_found", "Session not found")
        candidates = [session]
    else:
        candidates = AttendanceSession.query.filter_by(
            institution_id=student.institution_id,
            section_id=student.section_id,
        ).all()

    now = utcnow()

    # Validate institution + class/section membership, session state,
    # code and time window (§10) — in that order.
    matched = None
    membership_error = None
    for cand in candidates:
        if cand.section_id != student.section_id:
            membership_error = api_error(
                403, "wrong_class",
                "You are not a member of this class/section"
            )
            continue
        try:
            session_open(cand, now=now)
        except CheckinError as exc:
            # keep state errors for the explicitly requested session only
            if session_id:
                return api_error(exc.status, exc.code, exc.message)
            continue
        if cand.code != code:
            continue
        if now > as_utc(cand.code_expires_at):
            return api_error(400, "code_expired",
                             "This attendance code has expired")
        matched = cand
        break

    if matched is None:
        if membership_error and session_id:
            return membership_error
        if not session_id:
            # distinguish expired-but-correct code for better UX
            for cand in candidates:
                if (cand.section_id == student.section_id
                        and cand.code == code
                        and now > as_utc(cand.code_expires_at)):
                    return api_error(400, "code_expired",
                                     "This attendance code has expired")
        return api_error(400, "invalid_code", "Invalid attendance code")

    if not session_id and matched is None:  # pragma: no cover
        return api_error(400, "invalid_code", "Invalid attendance code")

    # Duplicate check: application logic AND DB unique constraint (§10)
    existing = AttendanceRecord.query.filter_by(
        session_id=matched.id, student_id=student.id
    ).first()
    if existing is not None:
        return api_error(409, "already_marked",
                         f"Already marked {existing.status} for this session")

    status = classify(matched.scheduled_start_at, matched.institution, now=now)
    if status is None:
        return api_error(409, "checkin_window_closed",
                         "The check-in window for this session has passed")

    record = AttendanceRecord(
        institution_id=matched.institution_id,
        session_id=matched.id,
        student_id=student.id,
        status=status,
        recorded_at=now,  # server time authoritative (§11)
    )
    db.session.add(record)
    try:
        db.session.commit()
    except Exception:  # IntegrityError from the unique constraint
        db.session.rollback()
        existing = AttendanceRecord.query.filter_by(
            session_id=matched.id, student_id=student.id
        ).first()
        if existing is not None:
            return api_error(409, "already_marked",
                             f"Already marked {existing.status}")
        raise
    return jsonify({
        "message": "Attendance recorded",
        "status": record.status,
        "record": _record_json(record),
    }), 201


@bp.get("/attendance/today")
@require_role("STUDENT")
def today():
    student = _get_student(g.user)
    if student is None:
        return api_error(403, "no_student_profile",
                         "Account has no student profile")
    now = utcnow()
    records = AttendanceRecord.query.filter_by(
        student_id=student.id
    ).filter(
        db.func.date(AttendanceRecord.recorded_at) == db.func.date(now)
    ).order_by(AttendanceRecord.recorded_at).all()
    return jsonify({"date": now.date().isoformat(),
                    "records": [_record_json(r) for r in records]})


@bp.get("/attendance/history")
@require_role("STUDENT")
def history():
    student = _get_student(g.user)
    if student is None:
        return api_error(403, "no_student_profile",
                         "Account has no student profile")
    page = max(1, request.args.get("page", 1, type=int))
    per_page = min(100, request.args.get("per_page", 20, type=int))
    query = AttendanceRecord.query.filter_by(student_id=student.id)
    subject_id = request.args.get("subject_id", type=int)
    if subject_id:
        query = query.join(AttendanceSession).filter(
            AttendanceSession.subject_id == subject_id
        )
    pagination = query.order_by(
        AttendanceRecord.recorded_at.desc()
    ).paginate(page=page, per_page=per_page, error_out=False)
    return jsonify({
        "records": [_record_json(r) for r in pagination.items],
        "page": pagination.page,
        "per_page": pagination.per_page,
        "total": pagination.total,
    })


@bp.get("/attendance/summary")
@require_role("STUDENT")
def summary():
    """Subject-wise attendance and overall percentage (§8)."""
    student = _get_student(g.user)
    if student is None:
        return api_error(403, "no_student_profile",
                         "Account has no student profile")
    records = AttendanceRecord.query.filter_by(student_id=student.id).all()
    by_subject = {}
    for record in records:
        subject = record.session.subject
        key = subject.id if subject else 0
        bucket = by_subject.setdefault(key, {
            "subject_id": key,
            "subject": subject.name if subject else "Unknown",
            "total": 0, "present": 0, "late": 0,
        })
        bucket["total"] += 1
        if record.status == MarkStatus.PRESENT:
            bucket["present"] += 1
        else:
            bucket["late"] += 1
    subjects = []
    total = present_total = 0
    for bucket in by_subject.values():
        attended = bucket["present"] + bucket["late"]
        bucket["percentage"] = round(
            100.0 * attended / bucket["total"], 1
        ) if bucket["total"] else 0.0
        subjects.append(bucket)
        total += bucket["total"]
        present_total += attended
    return jsonify({
        "overall": {
            "total": total,
            "attended": present_total,
            "percentage": round(100.0 * present_total / total, 1)
            if total else 0.0,
        },
        "subjects": subjects,
    })
