"""Reporting endpoints (blueprint §13: GET /reports/*).

GET /reports/attendance      – daily institution-wide summary (?date=)
GET /reports/class/<id>      – per-student summary for a section (?from,&to)
GET /reports/student/<id>    – one student's record with percentage
"""
from datetime import date, datetime, timedelta

from flask import Blueprint, g, jsonify, request

from app.models import (
    AttendanceRecord, AttendanceSession, MarkStatus, Section, Student,
)
from app.utils import STAFF_ROLES, api_error, require_role

bp = Blueprint("reports", __name__)


def _parse_date(value, fallback):
    if not value:
        return fallback
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return fallback


@bp.get("/reports/attendance")
@require_role(*STAFF_ROLES)
def daily_report():
    inst_id = g.user.institution_id
    day = _parse_date(request.args.get("date"), date.today())
    sessions = [
        s for s in AttendanceSession.query.filter_by(
            institution_id=inst_id
        ).all() if s.scheduled_start_at.date() == day
    ]
    per_session = []
    totals = {"present": 0, "late": 0}
    for session in sessions:
        records = AttendanceRecord.query.filter_by(
            session_id=session.id
        ).all()
        present = sum(1 for r in records if r.status == MarkStatus.PRESENT)
        late = sum(1 for r in records if r.status == MarkStatus.LATE)
        enrolled = len(session.section.students)
        totals["present"] += present
        totals["late"] += late
        per_session.append({
            "session_id": session.id,
            "subject": session.subject.name,
            "section": session.section.name,
            "status": session.status,
            "enrolled": enrolled,
            "present": present,
            "late": late,
            "not_marked": max(0, enrolled - present - late),
        })
    return jsonify({"date": day.isoformat(), "sessions": per_session,
                    "totals": totals})


@bp.get("/reports/class/<int:section_id>")
@require_role(*STAFF_ROLES)
def class_report(section_id):
    section = Section.query.filter_by(
        id=section_id, institution_id=g.user.institution_id
    ).first()
    if section is None:
        return api_error(404, "not_found", "Section not found")
    date_from = _parse_date(
        request.args.get("from"),
        date.today() - timedelta(days=30),
    )
    date_to = _parse_date(request.args.get("to"), date.today())
    sessions = [
        s for s in AttendanceSession.query.filter_by(
            section_id=section.id
        ).all() if date_from <= s.scheduled_start_at.date() <= date_to
    ]
    session_ids = [s.id for s in sessions]
    records = AttendanceRecord.query.filter(
        AttendanceRecord.session_id.in_(session_ids)
        if session_ids else AttendanceRecord.id.is_(None)
    ).all()

    rows = []
    for student in section.students:
        mine = [r for r in records if r.student_id == student.id]
        present = sum(1 for r in mine if r.status == MarkStatus.PRESENT)
        late = sum(1 for r in mine if r.status == MarkStatus.LATE)
        attended = present + late
        rows.append({
            "student_id": student.id,
            "roll_no": student.roll_no,
            "full_name": student.user.full_name,
            "present": present,
            "late": late,
            "missed": max(0, len(sessions) - attended),
            "percentage": round(100.0 * attended / len(sessions), 1)
            if sessions else 0.0,
        })
    rows.sort(key=lambda r: r["roll_no"])
    return jsonify({
        "section": {"id": section.id, "name": section.name,
                    "klass": section.klass.name},
        "from": date_from.isoformat(),
        "to": date_to.isoformat(),
        "sessions_held": len(sessions),
        "students": rows,
    })


@bp.get("/reports/student/<int:student_id>")
@require_role(*STAFF_ROLES)
def student_report(student_id):
    student = Student.query.filter_by(
        id=student_id, institution_id=g.user.institution_id
    ).first()
    if student is None:
        return api_error(404, "not_found", "Student not found")
    records = AttendanceRecord.query.filter_by(
        student_id=student.id
    ).order_by(AttendanceRecord.recorded_at).all()
    by_subject = {}
    for record in records:
        subject = record.session.subject
        bucket = by_subject.setdefault(subject.id, {
            "subject_id": subject.id, "subject": subject.name,
            "present": 0, "late": 0,
        })
        bucket["present" if record.status == MarkStatus.PRESENT else "late"] += 1
    total = len(records)
    return jsonify({
        "student": {
            "id": student.id,
            "roll_no": student.roll_no,
            "full_name": student.user.full_name,
            "section": student.section.name,
        },
        "total_marked": total,
        "subjects": list(by_subject.values()),
        "records": [
            {
                "id": r.id,
                "session_id": r.session_id,
                "subject": r.session.subject.name,
                "status": r.status,
                "recorded_at": r.recorded_at.isoformat(),
                "is_corrected": bool(r.is_corrected),
            } for r in records
        ],
    })
