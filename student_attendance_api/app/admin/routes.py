"""Admin endpoints (blueprint §13) + master-data reads the dashboard needs.

POST /admin/students | /admin/teachers | /admin/classes | /admin/subjects
POST /admin/sections | /admin/assignments            (practical extensions)
POST /admin/attendance/{id}/correct                  (reason + audit, §10)
GET  /admin/*                                        (list endpoints)
"""
from datetime import date

from flask import Blueprint, g, jsonify, request

from app.extensions import db
from app.models import (
    AcademicYear, AuditLog, AttendanceRecord, Klass, Program, Role,
    Section, Student, Subject, SubjectAssignment, Teacher, User, utcnow,
)
from app.utils import ADMIN_ROLES, STAFF_ROLES, api_error, require_role

bp = Blueprint("admin", __name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _current_year(institution_id):
    year = AcademicYear.query.filter_by(
        institution_id=institution_id, is_current=True
    ).first()
    if year is None:
        year = AcademicYear.query.filter_by(
            institution_id=institution_id
        ).order_by(AcademicYear.start_date.desc()).first()
    if year is None:
        today = date.today()
        year = AcademicYear(
            institution_id=institution_id,
            name=f"{today.year}-{today.year + 1}",
            start_date=date(today.year, 1, 1),
            end_date=date(today.year, 12, 31),
            is_current=True,
        )
        db.session.add(year)
        db.session.flush()
    return year


def _section_json(section):
    return {
        "id": section.id,
        "name": section.name,
        "class_id": section.class_id,
        "klass": section.klass.name,
        "student_count": len(section.students),
    }


def _klass_json(klass):
    return {
        "id": klass.id,
        "name": klass.name,
        "program_id": klass.program_id,
        "program": klass.program.name,
        "academic_year_id": klass.academic_year_id,
        "sections": [_section_json(s) for s in klass.sections],
    }


def _user_json(user, extra=None):
    payload = {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role,
        "is_active": user.is_active,
    }
    if extra:
        payload.update(extra)
    return payload


# ---------------------------------------------------------------------------
# Create endpoints (§13)
# ---------------------------------------------------------------------------

@bp.post("/admin/students")
@require_role(*ADMIN_ROLES)
def create_student():
    data = request.get_json(silent=True) or {}
    required = ["email", "password", "full_name", "roll_no", "section_id"]
    missing = [f for f in required if not data.get(f)]
    if missing:
        return api_error(400, "validation_error",
                         f"Missing fields: {', '.join(missing)}")
    section = Section.query.filter_by(
        id=int(data["section_id"]), institution_id=g.user.institution_id
    ).first()
    if section is None:
        return api_error(404, "not_found", "Section not found")
    email = data["email"].strip().lower()
    if User.query.filter_by(email=email).first():
        return api_error(409, "exists", "Email already registered")
    user = User(
        institution_id=g.user.institution_id,
        email=email, full_name=data["full_name"],
        role=Role.STUDENT,
    )
    user.set_password(data["password"])
    student = Student(
        institution_id=g.user.institution_id,
        section_id=section.id, roll_no=data["roll_no"],
    )
    user.student = student
    db.session.add(user)
    db.session.commit()
    return jsonify(_user_json(user, {
        "student_id": student.id, "section_id": section.id,
        "roll_no": student.roll_no,
    })), 201


@bp.post("/admin/teachers")
@require_role(*ADMIN_ROLES)
def create_teacher():
    data = request.get_json(silent=True) or {}
    for field in ("email", "password", "full_name"):
        if not data.get(field):
            return api_error(400, "validation_error",
                             f"{field} is required")
    email = data["email"].strip().lower()
    if User.query.filter_by(email=email).first():
        return api_error(409, "exists", "Email already registered")
    user = User(
        institution_id=g.user.institution_id,
        email=email, full_name=data["full_name"],
        role=Role.TEACHER,
    )
    user.set_password(data["password"])
    teacher = Teacher(
        institution_id=g.user.institution_id,
        employee_no=data.get("employee_no"),
    )
    user.teacher = teacher
    db.session.add(user)
    db.session.commit()
    return jsonify(_user_json(user, {
        "teacher_id": teacher.id,
        "employee_no": teacher.employee_no,
    })), 201


@bp.post("/admin/classes")
@require_role(*ADMIN_ROLES)
def create_class():
    data = request.get_json(silent=True) or {}
    if not data.get("name"):
        return api_error(400, "validation_error", "name is required")
    inst_id = g.user.institution_id

    program_id = data.get("program_id")
    if program_id:
        program = Program.query.filter_by(
            id=int(program_id), institution_id=inst_id
        ).first()
        if program is None:
            return api_error(404, "not_found", "Program not found")
    else:
        program_data = data.get("program") or {}
        program = Program(
            institution_id=inst_id,
            name=program_data.get("name") or data["name"],
            code=program_data.get("code") or "PROG",
        )
        db.session.add(program)
        db.session.flush()

    year_id = data.get("academic_year_id")
    if year_id:
        year = AcademicYear.query.filter_by(
            id=int(year_id), institution_id=inst_id
        ).first()
        if year is None:
            return api_error(404, "not_found", "Academic year not found")
    else:
        year = _current_year(inst_id)

    klass = Klass(
        institution_id=inst_id, program_id=program.id,
        academic_year_id=year.id, name=data["name"],
    )
    db.session.add(klass)
    db.session.commit()
    return jsonify(_klass_json(klass)), 201


@bp.post("/admin/sections")
@require_role(*ADMIN_ROLES)
def create_section():
    data = request.get_json(silent=True) or {}
    if not data.get("name") or not data.get("class_id"):
        return api_error(400, "validation_error",
                         "name and class_id are required")
    klass = Klass.query.filter_by(
        id=int(data["class_id"]), institution_id=g.user.institution_id
    ).first()
    if klass is None:
        return api_error(404, "not_found", "Class not found")
    section = Section(
        institution_id=g.user.institution_id,
        class_id=klass.id, name=data["name"],
    )
    db.session.add(section)
    db.session.commit()
    return jsonify(_section_json(section)), 201


@bp.post("/admin/subjects")
@require_role(*ADMIN_ROLES)
def create_subject():
    data = request.get_json(silent=True) or {}
    if not data.get("name"):
        return api_error(400, "validation_error", "name is required")
    subject = Subject(
        institution_id=g.user.institution_id,
        name=data["name"],
        code=data.get("code") or data["name"][:10].upper(),
    )
    db.session.add(subject)
    db.session.commit()
    return jsonify({"id": subject.id, "name": subject.name,
                    "code": subject.code}), 201


@bp.post("/admin/assignments")
@require_role(*ADMIN_ROLES)
def create_assignment():
    """Bind a teacher to a subject + section (§6 teacher assignment)."""
    data = request.get_json(silent=True) or {}
    for field in ("teacher_id", "subject_id", "section_id"):
        if not data.get(field):
            return api_error(400, "validation_error", f"{field} is required")
    inst_id = g.user.institution_id
    teacher = Teacher.query.filter_by(
        id=int(data["teacher_id"]), institution_id=inst_id
    ).first()
    subject = Subject.query.filter_by(
        id=int(data["subject_id"]), institution_id=inst_id
    ).first()
    section = Section.query.filter_by(
        id=int(data["section_id"]), institution_id=inst_id
    ).first()
    if not all([teacher, subject, section]):
        return api_error(404, "not_found",
                         "Teacher, subject or section not found")
    existing = SubjectAssignment.query.filter_by(
        subject_id=subject.id, section_id=section.id
    ).first()
    if existing:
        return api_error(409, "exists",
                         "Subject already assigned to this section")
    assignment = SubjectAssignment(
        institution_id=inst_id, teacher_id=teacher.id,
        subject_id=subject.id, section_id=section.id,
    )
    db.session.add(assignment)
    db.session.commit()
    return jsonify({"id": assignment.id, "teacher_id": teacher.id,
                    "subject_id": subject.id,
                    "section_id": section.id}), 201


# ---------------------------------------------------------------------------
# Correction workflow: reason + audit record required (§10/§13)
# ---------------------------------------------------------------------------

@bp.post("/admin/attendance/<int:record_id>/correct")
@require_role(*STAFF_ROLES)
def correct_attendance(record_id):
    data = request.get_json(silent=True) or {}
    new_status = (data.get("new_status") or "").upper()
    reason = (data.get("reason") or "").strip()
    if new_status not in ("PRESENT", "LATE"):
        return api_error(400, "validation_error",
                         "new_status must be PRESENT or LATE")
    if not reason:
        return api_error(400, "validation_error",
                         "A correction reason is required")
    record = AttendanceRecord.query.filter_by(
        id=record_id, institution_id=g.user.institution_id
    ).first()
    if record is None:
        return api_error(404, "not_found", "Attendance record not found")
    old_status = record.status
    record.status = new_status
    record.is_corrected = True
    db.session.add(AuditLog(
        institution_id=g.user.institution_id,
        actor_user_id=g.user.id,
        action="attendance.correct",
        entity_type="attendance_record",
        entity_id=record.id,
        reason=f"{old_status} -> {new_status}: {reason}",
        created_at=utcnow(),
    ))
    db.session.commit()
    return jsonify({
        "id": record.id,
        "status": record.status,
        "previous_status": old_status,
        "is_corrected": True,
    })


# ---------------------------------------------------------------------------
# List endpoints (dashboard data)
# ---------------------------------------------------------------------------

@bp.get("/admin/students")
@require_role(*ADMIN_ROLES)
def list_students():
    query = Student.query.filter_by(institution_id=g.user.institution_id)
    section_id = request.args.get("section_id", type=int)
    if section_id:
        query = query.filter_by(section_id=section_id)
    students = query.all()
    return jsonify({"students": [
        {
            "id": s.id,
            "user_id": s.user_id,
            "email": s.user.email,
            "full_name": s.user.full_name,
            "roll_no": s.roll_no,
            "section_id": s.section_id,
            "section": s.section.name,
            "class": s.section.klass.name,
        } for s in students
    ]})


@bp.get("/admin/teachers")
@require_role(*ADMIN_ROLES)
def list_teachers():
    teachers = Teacher.query.filter_by(
        institution_id=g.user.institution_id
    ).all()
    return jsonify({"teachers": [
        {
            "id": t.id,
            "user_id": t.user_id,
            "email": t.user.email,
            "full_name": t.user.full_name,
            "employee_no": t.employee_no,
        } for t in teachers
    ]})


@bp.get("/admin/classes")
@require_role(*ADMIN_ROLES)
def list_classes():
    classes = Klass.query.filter_by(
        institution_id=g.user.institution_id
    ).all()
    return jsonify({"classes": [_klass_json(k) for k in classes]})


@bp.get("/admin/sections")
@require_role(*ADMIN_ROLES)
def list_sections():
    sections = Section.query.filter_by(
        institution_id=g.user.institution_id
    ).all()
    return jsonify({"sections": [_section_json(s) for s in sections]})


@bp.get("/admin/subjects")
@require_role(*ADMIN_ROLES)
def list_subjects():
    subjects = Subject.query.filter_by(
        institution_id=g.user.institution_id
    ).all()
    return jsonify({"subjects": [
        {"id": s.id, "name": s.name, "code": s.code} for s in subjects
    ]})


@bp.get("/admin/assignments")
@require_role(*ADMIN_ROLES)
def list_assignments():
    assignments = SubjectAssignment.query.filter_by(
        institution_id=g.user.institution_id
    ).all()
    return jsonify({"assignments": [
        {
            "id": a.id,
            "teacher_id": a.teacher_id,
            "teacher": a.teacher.user.full_name,
            "subject_id": a.subject_id,
            "subject": a.subject.name,
            "section_id": a.section_id,
            "section": a.section.name,
        } for a in assignments
    ]})


@bp.get("/admin/audit-logs")
@require_role(*ADMIN_ROLES)
def list_audit_logs():
    from app.models import AuditLog
    logs = AuditLog.query.filter_by(
        institution_id=g.user.institution_id
    ).order_by(AuditLog.created_at.desc()).limit(200).all()
    return jsonify({"logs": [
        {
            "id": log.id,
            "actor": log.actor.email if log.actor else None,
            "action": log.action,
            "entity_type": log.entity_type,
            "entity_id": log.entity_id,
            "reason": log.reason,
            "created_at": log.created_at.isoformat(),
        } for log in logs
    ]})
