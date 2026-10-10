"""SQLAlchemy models — blueprint §6 (academic data model) and §7 (tables).

Every tenant-scoped table carries institution_id so isolation can be
enforced at query time (blueprint §16 "Tenant isolation").
"""
from datetime import datetime, timezone

from werkzeug.security import check_password_hash, generate_password_hash

from ..extensions import db


def utcnow():
    """Server time in UTC. Server time is always authoritative (§11)."""
    return datetime.now(timezone.utc)


def as_utc(value):
    """Normalize DB datetimes: SQLite returns naive values (stored as UTC),
    PostgreSQL returns aware ones. Compare everything in aware UTC."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


# ---------------------------------------------------------------------------
# Enums as plain constants (kept simple for V1)
# ---------------------------------------------------------------------------

class Role:
    SUPER_ADMIN = "SUPER_ADMIN"
    INSTITUTION_ADMIN = "INSTITUTION_ADMIN"
    HOD = "HOD"                # HOD / Academic Admin (§5)
    TEACHER = "TEACHER"
    STUDENT = "STUDENT"
    PARENT = "PARENT"
    ALL = {
        SUPER_ADMIN, INSTITUTION_ADMIN, HOD, TEACHER, STUDENT, PARENT,
    }


class SessionStatus:
    OPEN = "OPEN"
    CLOSED = "CLOSED"


class MarkStatus:
    PRESENT = "PRESENT"
    LATE = "LATE"


class LeaveStatus:
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


# ---------------------------------------------------------------------------
# Institution & academic structure
# ---------------------------------------------------------------------------

class Institution(db.Model):
    __tablename__ = "institutions"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    code = db.Column(db.String(50), unique=True, nullable=False)
    timezone = db.Column(db.String(60), nullable=False, default="UTC")
    # Configurable timing policy (§11) — all values institution-configurable
    present_window_minutes = db.Column(db.Integer, nullable=False, default=10)
    late_window_minutes = db.Column(db.Integer, nullable=False, default=10)
    # Short-lived code TTL, 30–60 s (§10)
    code_ttl_seconds = db.Column(db.Integer, nullable=False, default=45)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow)

    def checkin_cutoff(self, scheduled_start):
        """After this instant self check-in closes (§11)."""
        from datetime import timedelta
        return scheduled_start + timedelta(
            minutes=self.present_window_minutes + self.late_window_minutes
        )


class AcademicYear(db.Model):
    __tablename__ = "academic_years"

    id = db.Column(db.Integer, primary_key=True)
    institution_id = db.Column(
        db.Integer, db.ForeignKey("institutions.id"), nullable=False, index=True
    )
    name = db.Column(db.String(100), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    is_current = db.Column(db.Boolean, default=False)

    institution = db.relationship("Institution")


class Program(db.Model):
    """Program / Course / Grade (§6)."""

    __tablename__ = "programs"

    id = db.Column(db.Integer, primary_key=True)
    institution_id = db.Column(
        db.Integer, db.ForeignKey("institutions.id"), nullable=False, index=True
    )
    name = db.Column(db.String(200), nullable=False)
    code = db.Column(db.String(50), nullable=False)

    institution = db.relationship("Institution")


class Klass(db.Model):
    """Class / Year / Semester (§6). Table name 'classes' is reserved-ish
    in some SQL dialects, hence 'klasses' — exposed as 'classes' in the API.
    """

    __tablename__ = "klasses"

    id = db.Column(db.Integer, primary_key=True)
    institution_id = db.Column(
        db.Integer, db.ForeignKey("institutions.id"), nullable=False, index=True
    )
    program_id = db.Column(
        db.Integer, db.ForeignKey("programs.id"), nullable=False
    )
    academic_year_id = db.Column(
        db.Integer, db.ForeignKey("academic_years.id"), nullable=False
    )
    name = db.Column(db.String(100), nullable=False)

    institution = db.relationship("Institution")
    program = db.relationship("Program")
    academic_year = db.relationship("AcademicYear")
    sections = db.relationship("Section", back_populates="klass",
                               cascade="all, delete-orphan")


class Section(db.Model):
    __tablename__ = "sections"

    id = db.Column(db.Integer, primary_key=True)
    institution_id = db.Column(
        db.Integer, db.ForeignKey("institutions.id"), nullable=False, index=True
    )
    class_id = db.Column(db.Integer, db.ForeignKey("klasses.id"),
                         nullable=False)
    name = db.Column(db.String(50), nullable=False)

    institution = db.relationship("Institution")
    klass = db.relationship("Klass", back_populates="sections")
    students = db.relationship("Student", back_populates="section")


class Subject(db.Model):
    __tablename__ = "subjects"

    id = db.Column(db.Integer, primary_key=True)
    institution_id = db.Column(
        db.Integer, db.ForeignKey("institutions.id"), nullable=False, index=True
    )
    name = db.Column(db.String(200), nullable=False)
    code = db.Column(db.String(50), nullable=False)

    institution = db.relationship("Institution")


# ---------------------------------------------------------------------------
# People
# ---------------------------------------------------------------------------

class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    institution_id = db.Column(
        db.Integer, db.ForeignKey("institutions.id"), nullable=False, index=True
    )
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(300), nullable=False)
    full_name = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(30), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow)

    institution = db.relationship("Institution")
    teacher = db.relationship("Teacher", back_populates="user",
                              uselist=False, cascade="all, delete-orphan")
    student = db.relationship("Student", back_populates="user",
                              uselist=False, cascade="all, delete-orphan")
    parent = db.relationship("Parent", back_populates="user",
                             uselist=False, cascade="all, delete-orphan")

    def set_password(self, raw):
        # KDF strength is env-tunable so test suites can run fast while
        # production keeps the strong default (§16).
        import os
        method = os.environ.get("PASSWORD_HASH_METHOD", "pbkdf2:sha256")
        self.password_hash = generate_password_hash(raw, method=method)

    def check_password(self, raw):
        return check_password_hash(self.password_hash, raw)

    @property
    def is_admin(self):
        return self.role in {
            Role.SUPER_ADMIN, Role.INSTITUTION_ADMIN, Role.HOD,
        }

    @property
    def is_staff(self):
        return self.is_admin or self.role == Role.TEACHER


class Teacher(db.Model):
    __tablename__ = "teachers"

    id = db.Column(db.Integer, primary_key=True)
    institution_id = db.Column(
        db.Integer, db.ForeignKey("institutions.id"), nullable=False, index=True
    )
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"),
                        unique=True, nullable=False)
    employee_no = db.Column(db.String(50))

    user = db.relationship("User", back_populates="teacher")
    assignments = db.relationship("SubjectAssignment",
                                  back_populates="teacher")


class Student(db.Model):
    __tablename__ = "students"

    id = db.Column(db.Integer, primary_key=True)
    institution_id = db.Column(
        db.Integer, db.ForeignKey("institutions.id"), nullable=False, index=True
    )
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"),
                        unique=True, nullable=False)
    section_id = db.Column(db.Integer, db.ForeignKey("sections.id"),
                           nullable=False)
    roll_no = db.Column(db.String(50), nullable=False)

    user = db.relationship("User", back_populates="student")
    section = db.relationship("Section", back_populates="students")

    __table_args__ = (
        db.UniqueConstraint("institution_id", "roll_no",
                            name="uq_student_rollno_per_institution"),
    )


class Parent(db.Model):
    __tablename__ = "parents"

    id = db.Column(db.Integer, primary_key=True)
    institution_id = db.Column(
        db.Integer, db.ForeignKey("institutions.id"), nullable=False, index=True
    )
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"),
                        unique=True, nullable=False)

    user = db.relationship("User", back_populates="parent")
    children = db.relationship("ParentStudent", back_populates="parent",
                               cascade="all, delete-orphan")


class ParentStudent(db.Model):
    __tablename__ = "parent_students"

    id = db.Column(db.Integer, primary_key=True)
    parent_id = db.Column(db.Integer, db.ForeignKey("parents.id"),
                          nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"),
                           nullable=False)

    parent = db.relationship("Parent", back_populates="children")
    student = db.relationship("Student")


class SubjectAssignment(db.Model):
    """Teacher → subject ↔ section assignment (§6)."""

    __tablename__ = "subject_assignments"

    id = db.Column(db.Integer, primary_key=True)
    institution_id = db.Column(
        db.Integer, db.ForeignKey("institutions.id"), nullable=False, index=True
    )
    subject_id = db.Column(db.Integer, db.ForeignKey("subjects.id"),
                           nullable=False)
    section_id = db.Column(db.Integer, db.ForeignKey("sections.id"),
                           nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey("teachers.id"),
                           nullable=False)

    institution = db.relationship("Institution")
    subject = db.relationship("Subject")
    section = db.relationship("Section")
    teacher = db.relationship("Teacher", back_populates="assignments")

    __table_args__ = (
        db.UniqueConstraint("subject_id", "section_id",
                            name="uq_subject_section"),
    )


# ---------------------------------------------------------------------------
# Attendance
# ---------------------------------------------------------------------------

class AttendanceSession(db.Model):
    __tablename__ = "attendance_sessions"

    id = db.Column(db.Integer, primary_key=True)
    institution_id = db.Column(
        db.Integer, db.ForeignKey("institutions.id"), nullable=False, index=True
    )
    section_id = db.Column(db.Integer, db.ForeignKey("sections.id"),
                           nullable=False, index=True)
    subject_id = db.Column(db.Integer, db.ForeignKey("subjects.id"),
                           nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey("teachers.id"),
                           nullable=False)
    # Class start per institution timing policy (§11)
    scheduled_start_at = db.Column(db.DateTime(timezone=True), nullable=False)
    # Code lifecycle (§10): crypto-random 6-digit, short TTL, rotatable
    code = db.Column(db.String(6), nullable=False)
    code_expires_at = db.Column(db.DateTime(timezone=True), nullable=False)
    status = db.Column(db.String(10), nullable=False,
                       default=SessionStatus.OPEN)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow)
    closed_at = db.Column(db.DateTime(timezone=True))

    institution = db.relationship("Institution")
    section = db.relationship("Section")
    subject = db.relationship("Subject")
    teacher = db.relationship("Teacher")
    records = db.relationship("AttendanceRecord", back_populates="session",
                              cascade="all, delete-orphan")


class AttendanceRecord(db.Model):
    __tablename__ = "attendance_records"

    id = db.Column(db.Integer, primary_key=True)
    institution_id = db.Column(
        db.Integer, db.ForeignKey("institutions.id"), nullable=False, index=True
    )
    session_id = db.Column(
        db.Integer, db.ForeignKey("attendance_sessions.id"), nullable=False,
        index=True,
    )
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"),
                           nullable=False, index=True)
    status = db.Column(db.String(10), nullable=False)  # PRESENT | LATE
    recorded_at = db.Column(db.DateTime(timezone=True), nullable=False)
    # Corrections require a reason + audit record (§10)
    is_corrected = db.Column(db.Boolean, default=False)

    session = db.relationship("AttendanceSession", back_populates="records")
    student = db.relationship("Student")

    # Duplicate prevention: application logic AND a DB constraint (§10)
    __table_args__ = (
        db.UniqueConstraint("session_id", "student_id",
                            name="uq_session_student"),
    )


# ---------------------------------------------------------------------------
# Leaves, audit, subscriptions, notifications (§7)
# ---------------------------------------------------------------------------

class Leave(db.Model):
    __tablename__ = "leaves"

    id = db.Column(db.Integer, primary_key=True)
    institution_id = db.Column(
        db.Integer, db.ForeignKey("institutions.id"), nullable=False, index=True
    )
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"),
                           nullable=False)
    from_date = db.Column(db.Date, nullable=False)
    to_date = db.Column(db.Date, nullable=False)
    reason = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(12), nullable=False,
                       default=LeaveStatus.PENDING)
    reviewed_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow)

    student = db.relationship("Student")
    reviewer = db.relationship("User")


class AuditLog(db.Model):
    __tablename__ = "audit_logs"

    id = db.Column(db.Integer, primary_key=True)
    institution_id = db.Column(
        db.Integer, db.ForeignKey("institutions.id"), nullable=False, index=True
    )
    actor_user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    action = db.Column(db.String(100), nullable=False)
    entity_type = db.Column(db.String(50))
    entity_id = db.Column(db.Integer)
    reason = db.Column(db.Text)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow)

    actor = db.relationship("User")


class Subscription(db.Model):
    __tablename__ = "subscriptions"

    id = db.Column(db.Integer, primary_key=True)
    institution_id = db.Column(
        db.Integer, db.ForeignKey("institutions.id"), nullable=False, index=True
    )
    plan = db.Column(db.String(50), nullable=False, default="FREE")
    status = db.Column(db.String(20), nullable=False, default="ACTIVE")
    starts_at = db.Column(db.DateTime(timezone=True), default=utcnow)
    ends_at = db.Column(db.DateTime(timezone=True))

    institution = db.relationship("Institution")


class Notification(db.Model):
    __tablename__ = "notifications"

    id = db.Column(db.Integer, primary_key=True)
    institution_id = db.Column(
        db.Integer, db.ForeignKey("institutions.id"), nullable=False, index=True
    )
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"),
                        nullable=False)
    title = db.Column(db.String(200), nullable=False)
    body = db.Column(db.Text)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow)

    user = db.relationship("User")
