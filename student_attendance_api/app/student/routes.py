"""Student endpoints (blueprint §8/§13).

GET /student/dashboard – today's classes + attendance snapshot
GET /student/classes   – class/section/subjects with teachers
"""
from datetime import date

from flask import Blueprint, g, jsonify

from app.models import (
    AttendanceRecord, AttendanceSession, MarkStatus, Section,
    Student, SubjectAssignment, as_utc, utcnow,
)
from app.utils import api_error, require_role

bp = Blueprint("student", __name__)


def _get_student():
    return Student.query.filter_by(user_id=g.user.id).first()


@bp.get("/student/classes")
@require_role("STUDENT", "PARENT")
def my_classes():
    student = _get_student()
    if student is None:
        return api_error(403, "no_student_profile",
                         "Account has no student profile")
    section = student.section
    klass = section.klass
    assignments = SubjectAssignment.query.filter_by(
        section_id=section.id
    ).all()
    subjects = [
        {
            "subject_id": a.subject_id,
            "subject": a.subject.name,
            "subject_code": a.subject.code,
            "teacher": a.teacher.user.full_name if a.teacher and a.teacher.user else None,
        }
        for a in assignments
    ]
    return jsonify({
        "institution": {
            "id": g.user.institution_id,
            "name": section.institution.name,
            "timezone": section.institution.timezone,
        },
        "program": {
            "id": klass.program_id,
            "name": klass.program.name,
        },
        "class": {"id": klass.id, "name": klass.name},
        "section": {"id": section.id, "name": section.name},
        "roll_no": student.roll_no,
        "subjects": subjects,
    })


@bp.get("/student/dashboard")
@require_role("STUDENT")
def dashboard():
    student = _get_student()
    if student is None:
        return api_error(403, "no_student_profile",
                         "Account has no student profile")

    now = utcnow()
    today = now.date()

    # Today's classes = sessions scheduled today for the student's section
    sessions = AttendanceSession.query.filter_by(
        section_id=student.section_id
    ).all()
    todays = []
    marked_session_ids = set()
    for record in AttendanceRecord.query.filter_by(
            student_id=student.id).all():
        marked_session_ids.add(record.session_id)

    for session in sessions:
        if session.scheduled_start_at.date() != today:
            continue
        todays.append({
            "session_id": session.id,
            "subject": session.subject.name,
            "scheduled_start_at": session.scheduled_start_at.isoformat(),
            "status": session.status,
            "marked": session.id in marked_session_ids,
            "my_status": next(
                (r.status for r in AttendanceRecord.query.filter_by(
                    session_id=session.id, student_id=student.id).all()),
                None,
            ),
        })
    todays.sort(key=lambda item: item["scheduled_start_at"])

    records = AttendanceRecord.query.filter_by(student_id=student.id).all()
    held_sessions = [
        s for s in sessions if as_utc(s.scheduled_start_at) <= now
    ]
    attended = sum(1 for s in held_sessions if s.id in marked_session_ids)
    by_status = {
        MarkStatus.PRESENT: sum(
            1 for r in records if r.status == MarkStatus.PRESENT
        ),
        MarkStatus.LATE: sum(
            1 for r in records if r.status == MarkStatus.LATE
        ),
    }
    from app.models import Leave, LeaveStatus
    pending_leaves = Leave.query.filter_by(
        student_id=student.id, status=LeaveStatus.PENDING
    ).count()

    return jsonify({
        "today": today.isoformat(),
        "classes": todays,
        "attendance": {
            "sessions_held": len(held_sessions),
            "attended": attended,
            "percentage": round(100.0 * attended / len(held_sessions), 1)
            if held_sessions else 0.0,
            "by_status": by_status,
        },
        "pending_leaves": pending_leaves,
    })
