"""The generated academic data, checked as a whole and through the real calculations."""
import json
from collections import Counter

import pytest
from alembic import command
from sqlalchemy.orm import sessionmaker

from app.core.config import DATA_DIR
from app.db import session as db_session
from app.db.seed import seed
from app.services import academic_service as svc
from test_db_setup import _alembic_config


def load(name):
    return json.loads((DATA_DIR / f"{name}.json").read_text())


COURSES = {c["course_code"]: c for c in load("courses")}
RECORDS = load("academic_records")
PROFILES = {p["student_id"]: p for p in load("student_profiles")}
STUDENTS = {s["student_id"]: s for s in load("students")}


def test_every_record_refers_to_a_real_course_in_the_right_semester():
    for r in RECORDS:
        assert r["course_code"] in COURSES and COURSES[r["course_code"]]["semester"] == r["semester"]


def test_every_record_is_possible():
    assert all(0 <= r["attended"] <= r["total"] for r in RECORDS)
    assert all(r["grade"] in (None, "O", "A+", "A", "B+", "B", "C", "P", "F") for r in RECORDS)


def test_one_record_per_student_and_course():
    assert max(Counter((r["student_id"], r["course_code"]) for r in RECORDS).values()) == 1


def test_every_student_has_a_profile_in_the_right_semester():
    assert set(PROFILES) == set(STUDENTS)
    for student_id, student in STUDENTS.items():
        assert PROFILES[student_id]["semester"] == svc.default_semester(student["year"])


def test_a_student_only_takes_their_own_departments_courses():
    for r in RECORDS:
        assert COURSES[r["course_code"]]["department"] == STUDENTS[r["student_id"]]["program"]


def test_grades_exist_exactly_for_completed_semesters():
    for r in RECORDS:
        completed = r["semester"] < PROFILES[r["student_id"]]["semester"]
        assert (r["grade"] is not None) == completed


@pytest.fixture(scope="module")
def seeded_factory(tmp_path_factory):
    """The real seed data, loaded once into a migrated database."""
    url = f"sqlite:///{tmp_path_factory.mktemp('academic') / 'seeded.db'}"
    command.upgrade(_alembic_config(url), "head")
    engine = db_session.make_engine(url)
    factory = sessionmaker(engine, expire_on_commit=False)
    with factory() as session:
        seed(session)
    yield factory
    engine.dispose()


@pytest.fixture
def seeded(seeded_factory, monkeypatch):
    monkeypatch.setattr(db_session, "SessionLocal", seeded_factory)


def test_the_demo_student_has_attendance_worth_talking_about(seeded):
    report = svc.attendance_report("1RV23IS101")
    by_code = {c["course_code"]: c for c in report["courses"]}
    assert report["semester"] == 5 and by_code["IS501"]["percentage"] == 72.0 and by_code["IS501"]["status"] == "short"
    assert by_code["IS501"]["classes_to_reach_75"] == 3
    assert report["below_required"] == ["IS501", "IS504"]


def test_one_student_is_below_the_condonation_line(seeded):
    course = next(c for c in svc.attendance_report("1RV22EC088")["courses"] if c["course_code"] == "EC705")
    assert course["status"] == "critical"


def test_one_student_carries_a_backlog(seeded):
    result = svc.cgpa("1RV22CS220")
    assert [b["course_code"] for b in result["backlogs"]] == ["CS203"]


def test_every_cgpa_is_plausible_and_first_years_have_none(seeded):
    for student_id, student in STUDENTS.items():
        result = svc.cgpa(student_id)
        if student["year"] == 1:
            assert result["cgpa"] is None
        else:
            assert 4.0 <= result["cgpa"] <= 10.0, student_id
            assert len(result["semesters"]) == svc.default_semester(student["year"]) - 1


def test_every_student_has_a_full_attendance_report(seeded):
    for student_id in STUDENTS:
        assert len(svc.attendance_report(student_id)["courses"]) >= 4
