"""Teacher endpoints (blueprint §9/§13): session lifecycle.

POST /teacher/sessions                – start attendance (6-digit code)
GET  /teacher/sessions                – session history
GET  /teacher/sessions/{id}           – live present/late count + code
POST /teacher/sessions/{id}/close     – close session
POST /teacher/sessions/{id}/rotate-code – fresh short-lived code (§10 rotation)
"""
from datetime import timedelta

from flask import Blueprint, g, jsonify, request
from zoneinfo import ZoneInfo

from app.extensions import db
from app.models import (
    AttendanceRecord, AttendanceSession, MarkStatus, Section, SessionStatus,
    Subject, SubjectAssignment, Teacher, as_utc, utcnow,
)
from app.utils import ADMIN_ROLES, STAFF_ROLES, api_error, require_role
from app.utils.security import generate_attendance_code

bp = Blueprint("teacher", __name__)


def _parse_when(value, institution):
    """Parse scheduled start; naive values are institution-local time (§11)."""
    if not value:
        return utcnow()
    try:
        when = datetime_from_iso(value)
    except (ValueError, TypeError):
        raise ValueError("scheduled_start_at must be an ISO-8601 datetime")
    if when.tzinfo is None:
        try:
            tz = ZoneInfo(institution.timezone)
        except Exception:
            tz = ZoneInfo("UTC")
        when = when.replace(tzinfo=tz)
    return when.astimezone(ZoneInfo("UTC"))


def datetime_from_iso(value):
    from datetime import datetime
    text = value.strip().replace("Z", "+00:00")
    return datetime.fromisoformat(text)


def _can_teach(user, subject_id, section_id):
    if user.role in ADMIN_ROLES:
        return True
    teacher = Teacher.query.filter_by(user_id=user.id).first()
    if teacher is None:
        return False
    return SubjectAssignment.query.filter_by(
        teacher_id=teacher.id, subject_id=subject_id, section_id=section_id
    ).first() is not None


def _session_json(session, include_code=False, now=None):
    now = now or utcnow()
    records = AttendanceRecord.query.filter_by(session_id=session.id).all()
    present = sum(1 for r in records if r.status == MarkStatus.PRESENT)
    late = sum(1 for r in records if r.status == MarkStatus.LATE)
    expires = as_utc(session.code_expires_at)
    code_valid = expires >= now and session.status == SessionStatus.OPEN
    payload = {
        "id": session.id,
        "section_id": session.section_id,
        "section": session.section.name if session.section else None,
        "klass": session.section.klass.name if session.section else None,
        "subject_id": session.subject_id,
        "subject": session.subject.name if session.subject else None,
        "teacher_id": session.teacher_id,
        "scheduled_start_at": session.scheduled_start_at.isoformat(),
        "status": session.status,
        "present_count": present,
        "late_count": late,
        "total_marked": present + late,
        "code_expires_at": expires.isoformat(),
        "code_valid": code_valid,
        "code_seconds_left": max(
            0, int((expires - now).total_seconds())
        ),
        "created_at": session.created_at.isoformat() if session.created_at else None,
        "closed_at": session.closed_at.isoformat() if session.closed_at else None,
        "checkin_cutoff": session.institution.checkin_cutoff(
            session.scheduled_start_at
        ).isoformat(),
    }
    if include_code:
        payload["code"] = session.code
    return payload


@bp.get("/teacher/options")
@require_role(*STAFF_ROLES)
def staff_options():
    """Sections/subjects/assignments the signed-in staff may use.

    Teachers cannot call /admin/* (§16 role separation), so the dashboard
    and app read their pick-lists from here.
    """
    user = g.user
    inst_id = user.institution_id
    sections = Section.query.filter_by(institution_id=inst_id).all()
    subjects = Subject.query.filter_by(institution_id=inst_id).all()
    assignment_query = SubjectAssignment.query.filter_by(
        institution_id=inst_id
    )
    if user.role == "TEACHER":
        teacher = Teacher.query.filter_by(user_id=user.id).first()
        assignment_query = assignment_query.filter_by(
            teacher_id=teacher.id if teacher else -1
        )
    assignments = assignment_query.all()
    return jsonify({
        "sections": [
            {"id": s.id, "name": f"{s.klass.name} — {s.name}",
             "class_id": s.class_id}
            for s in sections
        ],
        "subjects": [{"id": s.id, "name": s.name, "code": s.code}
                     for s in subjects],
        "assignments": [
            {"subject_id": a.subject_id, "section_id": a.section_id}
            for a in assignments
        ],
        "is_admin": user.is_admin,
    })


@bp.post("/teacher/sessions")
@require_role(*STAFF_ROLES)
def create_session():
    data = request.get_json(silent=True) or {}
    section_id = data.get("section_id")
    subject_id = data.get("subject_id")
    if not section_id or not subject_id:
        return api_error(400, "validation_error",
                         "section_id and subject_id are required")

    user = g.user
    section = Section.query.filter_by(
        id=section_id, institution_id=user.institution_id
    ).first()
    subject = Subject.query.filter_by(
        id=subject_id, institution_id=user.institution_id
    ).first()
    if section is None or subject is None:
        return api_error(404, "not_found", "Section or subject not found")

    if not _can_teach(user, subject.id, section.id):
        return api_error(403, "forbidden",
                         "You are not assigned to teach this subject here")

    teacher = Teacher.query.filter_by(user_id=user.id).first()
    if teacher is None:
        if user.role not in ADMIN_ROLES:
            return api_error(400, "no_teacher_profile",
                             "No teacher profile linked to this account")
        # Admins/HODs may run a session ad hoc — provision their profile once.
        teacher = Teacher(institution_id=user.institution_id, user_id=user.id)
        db.session.add(teacher)
        db.session.flush()

    inst = section.institution
    now = utcnow()
    try:
        scheduled = _parse_when(data.get("scheduled_start_at"), inst)
    except ValueError as exc:
        return api_error(400, "validation_error", str(exc))

    session = AttendanceSession(
        institution_id=user.institution_id,
        section_id=section.id,
        subject_id=subject.id,
        teacher_id=teacher.id,
        scheduled_start_at=scheduled,
        code=generate_attendance_code(),
        code_expires_at=now + timedelta(seconds=inst.code_ttl_seconds),
        status=SessionStatus.OPEN,
        created_at=now,
    )
    db.session.add(session)
    db.session.commit()
    return jsonify(_session_json(session, include_code=True, now=now)), 201


@bp.get("/teacher/sessions")
@require_role(*STAFF_ROLES)
def session_history():
    user = g.user
    query = AttendanceSession.query.filter_by(
        institution_id=user.institution_id
    )
    status = request.args.get("status")
    if status:
        query = query.filter_by(status=status)
    section_id = request.args.get("section_id")
    if section_id:
        query = query.filter_by(section_id=int(section_id))
    sessions = query.order_by(AttendanceSession.created_at.desc()).limit(100)
    return jsonify({"sessions": [_session_json(s) for s in sessions]})


@bp.get("/teacher/sessions/<int:session_id>")
@require_role(*STAFF_ROLES)
def get_session(session_id):
    session = AttendanceSession.query.filter_by(
        id=session_id, institution_id=g.user.institution_id
    ).first()
    if session is None:
        return api_error(404, "not_found", "Session not found")
    # The teacher who owns the session (or any admin) sees the live code.
    show_code = (
        g.user.role in ADMIN_ROLES or session.teacher.user_id == g.user.id
    )
    return jsonify(_session_json(session, include_code=show_code))


@bp.post("/teacher/sessions/<int:session_id>/close")
@require_role(*STAFF_ROLES)
def close_session(session_id):
    session = AttendanceSession.query.filter_by(
        id=session_id, institution_id=g.user.institution_id
    ).first()
    if session is None:
        return api_error(404, "not_found", "Session not found")
    if session.status == SessionStatus.CLOSED:
        return api_error(409, "already_closed", "Session is already closed")
    session.status = SessionStatus.CLOSED
    session.closed_at = utcnow()
    db.session.commit()
    return jsonify(_session_json(session))


@bp.post("/teacher/sessions/<int:session_id>/rotate-code")
@require_role(*STAFF_ROLES)
def rotate_code(session_id):
    """Codes expire/rotate after ~30–60 s (§10); the teacher's screen shows
    a countdown and can request a fresh code while the session is open."""
    session = AttendanceSession.query.filter_by(
        id=session_id, institution_id=g.user.institution_id
    ).first()
    if session is None:
        return api_error(404, "not_found", "Session not found")
    if session.status != SessionStatus.OPEN:
        return api_error(409, "session_closed",
                         "Cannot rotate code of a closed session")
    now = utcnow()
    inst = session.institution
    if now > as_utc(inst.checkin_cutoff(as_utc(session.scheduled_start_at))):
        return api_error(409, "checkin_window_closed",
                         "The check-in window for this session has passed")
    session.code = generate_attendance_code()
    session.code_expires_at = now + timedelta(seconds=inst.code_ttl_seconds)
    db.session.commit()
    return jsonify(_session_json(session, include_code=True, now=now))
