"""Leave request endpoints (blueprint §13).

POST /leave/requests          – student submits a request
GET  /leave/requests          – student: own; staff: institution-wide
POST /leave/requests/{id}/review – staff approves/rejects (extension)
"""
from datetime import datetime

from flask import Blueprint, g, jsonify, request

from app.extensions import db
from app.models import Leave, LeaveStatus, Role, Student, utcnow
from app.utils import STAFF_ROLES, api_error, require_auth, require_role

bp = Blueprint("leave", __name__)


def _parse_date(value):
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def _leave_json(leave):
    return {
        "id": leave.id,
        "student_id": leave.student_id,
        "student": leave.student.user.full_name if leave.student else None,
        "roll_no": leave.student.roll_no if leave.student else None,
        "section": leave.student.section.name if leave.student else None,
        "from_date": leave.from_date.isoformat(),
        "to_date": leave.to_date.isoformat(),
        "reason": leave.reason,
        "status": leave.status,
        "created_at": leave.created_at.isoformat(),
    }


@bp.post("/leave/requests")
@require_role("STUDENT")
def create_request():
    data = request.get_json(silent=True) or {}
    from_date = _parse_date(data.get("from_date"))
    to_date = _parse_date(data.get("to_date"))
    reason = (data.get("reason") or "").strip()
    if not from_date or not to_date:
        return api_error(400, "validation_error",
                         "from_date and to_date (YYYY-MM-DD) are required")
    if to_date < from_date:
        return api_error(400, "validation_error",
                         "to_date cannot be before from_date")
    if not reason:
        return api_error(400, "validation_error", "reason is required")
    student = Student.query.filter_by(user_id=g.user.id).first()
    if student is None:
        return api_error(403, "no_student_profile",
                         "Account has no student profile")
    leave = Leave(
        institution_id=g.user.institution_id,
        student_id=student.id,
        from_date=from_date, to_date=to_date, reason=reason,
        created_at=utcnow(),
    )
    db.session.add(leave)
    db.session.commit()
    return jsonify(_leave_json(leave)), 201


@bp.get("/leave/requests")
@require_auth
def list_requests():
    if g.user.role == Role.STUDENT:
        student = Student.query.filter_by(user_id=g.user.id).first()
        if student is None:
            return api_error(403, "no_student_profile",
                             "Account has no student profile")
        leaves = Leave.query.filter_by(student_id=student.id).order_by(
            Leave.created_at.desc()
        ).all()
    elif g.user.role == Role.PARENT:
        from app.models import Parent
        parent = Parent.query.filter_by(user_id=g.user.id).first()
        child_ids = [c.student_id for c in (parent.children if parent else [])]
        leaves = Leave.query.filter(
            Leave.student_id.in_(child_ids) if child_ids
            else Leave.id.is_(None)
        ).order_by(Leave.created_at.desc()).all()
    else:
        leaves = Leave.query.filter_by(
            institution_id=g.user.institution_id
        ).order_by(Leave.created_at.desc()).limit(200).all()
    return jsonify({"requests": [_leave_json(l) for l in leaves]})


@bp.post("/leave/requests/<int:leave_id>/review")
@require_role(*STAFF_ROLES)
def review_request(leave_id):
    data = request.get_json(silent=True) or {}
    decision = (data.get("decision") or "").upper()
    if decision not in ("APPROVED", "REJECTED"):
        return api_error(400, "validation_error",
                         "decision must be APPROVED or REJECTED")
    leave = Leave.query.filter_by(
        id=leave_id, institution_id=g.user.institution_id
    ).first()
    if leave is None:
        return api_error(404, "not_found", "Leave request not found")
    if leave.status != LeaveStatus.PENDING:
        return api_error(409, "already_reviewed",
                         "Leave request has already been reviewed")
    leave.status = decision
    leave.reviewed_by = g.user.id
    db.session.commit()
    return jsonify(_leave_json(leave))
