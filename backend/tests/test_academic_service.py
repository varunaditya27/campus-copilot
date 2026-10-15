import math

import pytest

from app.db.models import AcademicRecord, Course, StudentProfile
from app.models.academic import Preferences
from app.services import academic_service as svc
from helpers import add_academic_data

ASHA, RAVI = "1RV23IS101", "1RV24IS219"


@pytest.mark.parametrize("year, semester", [(1, 1), (2, 3), (3, 5), (4, 7)])
def test_the_semester_follows_from_the_year(year, semester):
    assert svc.default_semester(year) == semester


# --- profile


def test_a_student_without_a_profile_row_gets_sensible_defaults(db):
    profile = svc.get_profile(ASHA)
    assert (profile.name, profile.year, profile.semester, profile.section) == ("Asha", 3, 5, None)
    assert profile.electives == [] and profile.preferences.interests == []


def test_an_unknown_student_has_no_profile(db):
    assert svc.get_profile("1RV99ZZ999") is None
    assert svc.update_preferences("1RV99ZZ999", Preferences()) is None


def test_a_stored_profile_is_used_and_electives_are_named(db):
    add_academic_data(db)
    with db.begin() as session:
        session.add(StudentProfile(student_id=ASHA, semester=6, section="B", electives=["A501", "NOPE"], preferences={"interests": ["robotics"]}))

    profile = svc.get_profile(ASHA)

    assert (profile.semester, profile.section) == (6, "B")
    assert [(e.course_code, e.name, e.credits) for e in profile.electives] == [("A501", "Machine Learning", 4)]
    assert profile.preferences.interests == ["robotics"]


def test_updating_preferences_creates_the_profile_and_keeps_the_rest(db):
    updated = svc.update_preferences(ASHA, Preferences(interests=["robotics", "research"]))
    assert updated.preferences.interests == ["robotics", "research"] and updated.semester == 5


def test_a_second_update_replaces_the_first_and_is_saved(db):
    svc.update_preferences(ASHA, Preferences(interests=["robotics", "research"]))
    svc.update_preferences(ASHA, Preferences(interests=["cybersecurity"]))
    assert svc.get_profile(ASHA).preferences.interests == ["cybersecurity"]


def test_updating_preferences_leaves_the_semester_and_electives_alone(db):
    add_academic_data(db)
    with db.begin() as session:
        session.add(StudentProfile(student_id=ASHA, semester=6, section="B", electives=["A501"], preferences={}))
    svc.update_preferences(ASHA, Preferences(interests=["research"]))
    profile = svc.get_profile(ASHA)
    assert (profile.semester, profile.section, [e.course_code for e in profile.electives]) == (6, "B", ["A501"])


def test_repeated_interests_are_collapsed_in_order():
    assert Preferences(interests=["research", "robotics", "research"]).interests == ["research", "robotics"]


def test_at_most_six_interests_and_only_real_categories():
    with pytest.raises(ValueError):
        Preferences(interests=["cooking"])
    with pytest.raises(ValueError):
        Preferences(interests=["research"] * 7)


# --- attendance


def test_attendance_is_reported_subject_by_subject(db):
    add_academic_data(db)

    report = svc.attendance_report(ASHA)

    assert report["semester"] == 5 and report["required_percentage"] == 75.0
    assert {c["course_code"]: (c["percentage"], c["status"], c["classes_to_reach_75"]) for c in report["courses"]} == {
        "A501": (72.0, "short", 3),
        "A502": (96.4, "ok", 0),
        "A503": (50.0, "critical", 10),
    }
    assert report["below_required"] == ["A501", "A503"]


def test_only_the_running_semester_is_reported(db):
    add_academic_data(db)
    assert {c["course_code"] for c in svc.attendance_report(ASHA)["courses"]} == {"A501", "A502", "A503"}


def test_the_semester_comes_from_the_profile_when_there_is_one(db):
    add_academic_data(db)
    with db.begin() as session:
        session.add(StudentProfile(student_id=ASHA, semester=1, electives=[], preferences={}))
    assert [c["course_code"] for c in svc.attendance_report(ASHA)["courses"]] == ["A101", "A102"]


def test_each_students_report_is_their_own(db):
    add_academic_data(db)
    assert [c["course_code"] for c in svc.attendance_report(RAVI)["courses"]] == ["B301"]


def test_a_course_with_no_classes_yet_is_left_out(db):
    add_academic_data(db)
    with db.begin() as session:
        session.add(Course(course_code="A599", name="New", credits=1, department="ISE", semester=5, kind="lab"))
        session.flush()
        session.add(AcademicRecord(student_id=ASHA, course_code="A599", semester=5, attended=0, total=0, grade=None))
    assert "A599" not in {c["course_code"] for c in svc.attendance_report(ASHA)["courses"]}


@pytest.mark.parametrize("attended, total", [(18, 25), (5, 10), (0, 8), (30, 41), (1, 1), (40, 40)])
def test_the_classes_needed_are_exactly_enough_and_no_more(db, attended, total):
    add_academic_data(db)
    with db.begin() as session:
        record = session.query(AcademicRecord).filter_by(student_id=ASHA, course_code="A501").one()
        record.attended, record.total = attended, total

    needed = next(c for c in svc.attendance_report(ASHA)["courses"] if c["course_code"] == "A501")["classes_to_reach_75"]

    assert (attended + needed) / (total + needed) >= 0.75
    if needed:
        assert (attended + needed - 1) / (total + needed - 1) < 0.75


@pytest.mark.parametrize("attended, total, status", [(75, 100, "ok"), (74, 100, "short"), (65, 100, "short"), (64, 100, "critical")])
def test_the_policy_boundaries(db, attended, total, status):
    add_academic_data(db)
    with db.begin() as session:
        record = session.query(AcademicRecord).filter_by(student_id=ASHA, course_code="A501").one()
        record.attended, record.total = attended, total
    assert next(c for c in svc.attendance_report(ASHA)["courses"] if c["course_code"] == "A501")["status"] == status


def test_attendance_for_an_unknown_student_is_an_error(db):
    assert "error" in svc.attendance_report("1RV99ZZ999")


# --- CGPA


def test_sgpa_and_cgpa_are_credit_weighted(db):
    add_academic_data(db)

    result = svc.cgpa(ASHA)

    # semester 1: (4*8 + 3*7) / 7 = 7.57; semester 2: 10.0; overall: (32 + 21 + 40) / 11 = 8.45
    assert result["semesters"] == [{"semester": 1, "sgpa": 7.57}, {"semester": 2, "sgpa": 10.0}]
    assert result["cgpa"] == 8.45 and result["credits_counted"] == 11 and result["backlogs"] == []


def test_the_running_semester_has_no_grades_yet_so_it_is_not_counted(db):
    add_academic_data(db)
    assert {s["semester"] for s in svc.cgpa(ASHA)["semesters"]} == {1, 2}


def test_a_failed_course_counts_zero_points_but_keeps_its_credits(db):
    add_academic_data(db)
    with db.begin() as session:
        session.add(AcademicRecord(student_id=ASHA, course_code="A103", semester=1, attended=30, total=40, grade="F"))

    result = svc.cgpa(ASHA)

    assert result["semesters"][0] == {"semester": 1, "sgpa": 5.3}  # (32 + 21 + 0) / 10
    assert result["cgpa"] == 6.64  # 93 / 14
    assert result["backlogs"] == [{"course_code": "A103", "name": "Chemistry", "semester": 1}]


def test_a_student_with_no_results_has_no_cgpa(db):
    add_academic_data(db)
    result = svc.cgpa(RAVI)
    assert result["cgpa"] is None and result["semesters"] == [] and "No semester results" in result["message"]


def test_every_letter_grade_has_its_points():
    assert svc.GRADE_POINTS == {"O": 10, "A+": 9, "A": 8, "B+": 7, "B": 6, "C": 5, "P": 4, "F": 0}


def test_cgpa_for_an_unknown_student_is_an_error(db):
    assert "error" in svc.cgpa("1RV99ZZ999")


def test_the_database_refuses_impossible_records(db):
    from sqlalchemy.exc import IntegrityError

    add_academic_data(db)
    for fields in ({"attended": 30, "total": 20}, {"attended": -1, "total": 5}, {"grade": "Z"}):
        with pytest.raises(IntegrityError):
            with db.begin() as session:
                session.add(AcademicRecord(student_id=RAVI, course_code="A101", semester=1, **{"attended": 1, "total": 2, "grade": None, **fields}))


def test_one_record_per_student_and_course(db):
    from sqlalchemy.exc import IntegrityError

    add_academic_data(db)
    with pytest.raises(IntegrityError):
        with db.begin() as session:
            session.add(AcademicRecord(student_id=ASHA, course_code="A101", semester=1, attended=1, total=2, grade="A"))
