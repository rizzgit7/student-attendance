"""Shared fixtures: fresh in-memory DB per test, two institutions,
staff + students, helper factories.

Fixtures return *snapshots* (plain attribute bags) rather than live ORM
objects, because the seeding app-context ends before the test body runs.
"""
import os

# Fast KDF for tests only; production default stays strong (see models.User)
os.environ.setdefault("PASSWORD_HASH_METHOD", "pbkdf2:sha256:600")

import pytest

from app import create_app
from app.extensions import db as _db
from app.models import (
    AcademicYear, AttendanceSession, Institution, Klass, Program, Role,
    Section, Student, Subject, SubjectAssignment, Teacher, User,
)
from app.utils import ratelimit
from config import TestConfig


@pytest.fixture()
def app():
    app = create_app(TestConfig)
    with app.app_context():
        _db.create_all()
        yield app
        _db.session.remove()
        _db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture(autouse=True)
def clean_rate_limits():
    ratelimit.reset()
    yield
    ratelimit.reset()


def make_institution(name, code):
    inst = Institution(
        name=name, code=code, timezone="UTC",
        present_window_minutes=10, late_window_minutes=10,
        code_ttl_seconds=45,
    )
    _db.session.add(inst)
    _db.session.flush()
    return inst


def make_user(inst, email, password, role, name="User"):
    user = User(institution_id=inst.id, email=email, full_name=name,
                role=role)
    user.set_password(password)
    _db.session.add(user)
    _db.session.flush()
    return user


@pytest.fixture()
def seed(app):
    """Institution A with teacher + assignment + 2 sections (3 students);
    Institution B with a student + teacher for cross-tenant tests.

    Returns snapshots (plain objects) safe to use after the seeding
    app-context has been torn down.
    """

    class Snap:
        def __init__(self, **kw):
            self.__dict__.update(kw)

    def snap_user(u):
        return Snap(id=u.id, email=u.email, role=u.role,
                    institution_id=u.institution_id)

    with app.app_context():
        inst_a = make_institution("Test College", "TCA")
        inst_b = make_institution("Other College", "OCB")

        year = AcademicYear(
            institution_id=inst_a.id, name="2026-2027",
            start_date=__import__("datetime").date(2026, 1, 1),
            end_date=__import__("datetime").date(2026, 12, 31),
            is_current=True,
        )
        _db.session.add(year)
        _db.session.flush()

        program = Program(institution_id=inst_a.id, name="BSc",
                          code="BSC")
        _db.session.add(program)
        _db.session.flush()

        klass = Klass(institution_id=inst_a.id, program_id=program.id,
                      academic_year_id=year.id, name="Year 1")
        _db.session.add(klass)
        _db.session.flush()

        section1 = Section(institution_id=inst_a.id, class_id=klass.id,
                           name="A")
        section2 = Section(institution_id=inst_a.id, class_id=klass.id,
                           name="B")
        _db.session.add_all([section1, section2])
        _db.session.flush()

        subject = Subject(institution_id=inst_a.id, name="Mathematics",
                          code="MATH101")
        _db.session.add(subject)
        _db.session.flush()

        admin = make_user(inst_a, "admin@test.com", "AdminPass1!",
                          Role.INSTITUTION_ADMIN, "Admin One")
        teacher_user = make_user(inst_a, "teacher@test.com", "TeachPass1!",
                                 Role.TEACHER, "Tina Teacher")
        teacher = Teacher(institution_id=inst_a.id, user_id=teacher_user.id,
                          employee_no="T001")
        _db.session.add(teacher)
        _db.session.flush()

        assignment = SubjectAssignment(
            institution_id=inst_a.id, teacher_id=teacher.id,
            subject_id=subject.id, section_id=section1.id,
        )
        _db.session.add(assignment)

        students = []
        for idx, (email, section) in enumerate([
            ("s1@test.com", section1),
            ("s2@test.com", section1),
            ("s3@test.com", section2),
        ], start=1):
            user = make_user(inst_a, email, "StudentPass1!", Role.STUDENT,
                             f"Student {idx}")
            student = Student(
                institution_id=inst_a.id, user_id=user.id,
                section_id=section.id, roll_no=f"R{idx:03d}",
            )
            _db.session.add(student)
            students.append(student)

        # Institution B — student only (cross-tenant probes)
        user_b = make_user(inst_b, "sb@test.com", "StudentPass1!",
                           Role.STUDENT, "Foreign Student")
        inst_b_year = AcademicYear(
            institution_id=inst_b.id, name="2026-2027",
            start_date=__import__("datetime").date(2026, 1, 1),
            end_date=__import__("datetime").date(2026, 12, 31),
            is_current=True,
        )
        _db.session.add(inst_b_year)
        _db.session.flush()
        program_b = Program(institution_id=inst_b.id, name="BA", code="BA")
        _db.session.add(program_b)
        _db.session.flush()
        klass_b = Klass(institution_id=inst_b.id, program_id=program_b.id,
                        academic_year_id=inst_b_year.id, name="Year 1")
        _db.session.add(klass_b)
        _db.session.flush()
        section_b = Section(institution_id=inst_b.id, class_id=klass_b.id,
                            name="A")
        _db.session.add(section_b)
        _db.session.flush()
        student_b = Student(institution_id=inst_b.id, user_id=user_b.id,
                            section_id=section_b.id, roll_no="X001")
        _db.session.add(student_b)

        subject_b = Subject(institution_id=inst_b.id, name="History",
                            code="HIST101")
        _db.session.add(subject_b)
        _db.session.flush()
        teacher_b_user = make_user(inst_b, "teachb@test.com",
                                   "TeachPass1!", Role.TEACHER,
                                   "Foreign Teacher")
        teacher_b = Teacher(institution_id=inst_b.id,
                            user_id=teacher_b_user.id, employee_no="F001")
        _db.session.add(teacher_b)
        _db.session.flush()
        _db.session.add(SubjectAssignment(
            institution_id=inst_b.id, teacher_id=teacher_b.id,
            subject_id=subject_b.id, section_id=section_b.id,
        ))

        _db.session.commit()

        def snap_section(s):
            return Snap(id=s.id, name=s.name)

        return {
            "inst_a": Snap(id=inst_a.id, code=inst_a.code),
            "inst_b": Snap(id=inst_b.id, code=inst_b.code),
            "admin": snap_user(admin),
            "teacher_user": snap_user(teacher_user),
            "teacher": Snap(id=teacher.id),
            "subject": Snap(id=subject.id, name=subject.name),
            "section1": snap_section(section1),
            "section2": snap_section(section2),
            "s1": Snap(id=students[0].id, user=snap_user(students[0].user)),
            "s2": Snap(id=students[1].id),
            "s3": Snap(id=students[2].id),
            "student_b": Snap(id=student_b.id,
                              user=snap_user(user_b)),
            "teacher_b_user": snap_user(teacher_b_user),
            "subject_b": Snap(id=subject_b.id),
            "section_b": snap_section(section_b),
        }


def login(client, email, password):
    resp = client.post("/auth/login",
                       json={"email": email, "password": password})
    assert resp.status_code == 200, resp.get_json()
    body = resp.get_json()
    return {"Authorization": f"Bearer {body['access_token']}"}, body


def auth_headers(token_body):
    return {"Authorization": f"Bearer {token_body['access_token']}"}


def create_session(client, headers, section_id, subject_id, **extra):
    payload = {"section_id": section_id, "subject_id": subject_id}
    payload.update(extra)
    resp = client.post("/teacher/sessions", json=payload, headers=headers)
    assert resp.status_code == 201, resp.get_json()
    return resp.get_json()
