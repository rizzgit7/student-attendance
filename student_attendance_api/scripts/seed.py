"""Seed demo data for a local run (§20: remove demo data before production).

Usage:  python scripts/seed.py
"""
import os
import sys
from datetime import date, datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.extensions import db
from app.models import (
    AcademicYear, Institution, Klass, Program, Role, Section, Student,
    Subject, SubjectAssignment, Teacher, User,
)


def seed():
    app = create_app()
    with app.app_context():
        db.create_all()
        if Institution.query.filter_by(code="DEMO").first():
            print("Demo institution already seeded.")
            return

        inst = Institution(
            name="Demo College", code="DEMO", timezone="UTC",
            present_window_minutes=10, late_window_minutes=10,
            code_ttl_seconds=45,
        )
        db.session.add(inst)
        db.session.flush()

        year = AcademicYear(
            institution_id=inst.id, name="2026-2027",
            start_date=date(2026, 9, 1), end_date=date(2027, 6, 30),
            is_current=True,
        )
        program = Program(institution_id=inst.id, name="BSc Computer Science",
                          code="BSC-CS")
        db.session.add_all([year, program])
        db.session.flush()

        klass = Klass(institution_id=inst.id, program_id=program.id,
                      academic_year_id=year.id, name="Year 1")
        db.session.add(klass)
        db.session.flush()

        section_a = Section(institution_id=inst.id, class_id=klass.id,
                            name="A")
        db.session.add(section_a)
        db.session.flush()

        math = Subject(institution_id=inst.id, name="Mathematics",
                       code="MATH101")
        physics = Subject(institution_id=inst.id, name="Physics",
                          code="PHY101")
        db.session.add_all([math, physics])
        db.session.flush()

        admin = User(institution_id=inst.id, email="admin@demo.local",
                     full_name="Demo Admin", role=Role.INSTITUTION_ADMIN)
        admin.set_password("ChangeMe123!")

        teacher = User(institution_id=inst.id, email="teacher@demo.local",
                       full_name="Demo Teacher", role=Role.TEACHER)
        teacher.set_password("ChangeMe123!")
        teacher_profile = Teacher(institution_id=inst.id,
                                  employee_no="D001")
        teacher.teacher = teacher_profile
        db.session.add_all([admin, teacher])
        db.session.flush()

        db.session.add_all([
            SubjectAssignment(institution_id=inst.id,
                              teacher_id=teacher_profile.id,
                              subject_id=math.id, section_id=section_a.id),
            SubjectAssignment(institution_id=inst.id,
                              teacher_id=teacher_profile.id,
                              subject_id=physics.id,
                              section_id=section_a.id),
        ])

        for i in range(1, 4):
            user = User(institution_id=inst.id,
                        email=f"student{i}@demo.local",
                        full_name=f"Demo Student {i}", role=Role.STUDENT)
            user.set_password("ChangeMe123!")
            user.student = Student(institution_id=inst.id,
                                   section_id=section_a.id,
                                   roll_no=f"D{i:03d}")
            db.session.add(user)

        db.session.commit()
        print("Seeded demo institution 'DEMO':")
        print("  admin@demo.local / ChangeMe123!")
        print("  teacher@demo.local / ChangeMe123!")
        print("  student1..3@demo.local / ChangeMe123!")


if __name__ == "__main__":
    seed()
