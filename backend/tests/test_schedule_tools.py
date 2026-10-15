from datetime import date

import pytest
from pydantic import ValidationError

from app.core import clock
from app.services import academic_service, directory_service, fee_service, schedule_service
from helpers import add_schedule_data

ASHA = "1RV23IS101"
RAVI = "1RV24IS219"
MONDAY = date(2026, 10, 19)


@pytest.fixture
def data(db):
    add_schedule_data(db)


@pytest.fixture
def set_today(monkeypatch):
    def setter(day):
        monkeypatch.setattr(clock, "today", lambda: day)

    setter(MONDAY)
    return setter


def codes(classes):
    return [c["course_code"] for c in classes]


# --- timetable


def test_the_timetable_defaults_to_today(data, set_today):
    result = schedule_service.timetable(ASHA)
    assert (result["day"], result["date"]) == ("Monday", "2026-10-19")
    assert result["semester"] == 5 and result["section"] == "A"


def test_the_classes_come_in_time_order_with_their_details(data, set_today):
    first, second = schedule_service.timetable(ASHA)["classes"]
    assert first == {"start": "09:00", "end": "10:00", "course_code": "A501", "name": "Machine Learning", "kind": "theory", "room": "Classroom 5A"}
    assert (second["start"], second["course_code"]) == ("10:00", "A502")


def test_a_lab_block_shows_its_whole_span(data, set_today):
    (lab,) = schedule_service.timetable(ASHA, "Tuesday")["classes"]
    assert (lab["start"], lab["end"], lab["kind"], lab["room"]) == ("14:00", "16:00", "lab", "Lab 2")


@pytest.mark.parametrize("word", ["tuesday", "TUESDAY", "Tue", " tue "])
def test_a_weekday_can_be_named_in_any_style(data, set_today, word):
    assert schedule_service.timetable(ASHA, word)["day"] == "Tuesday"


def test_tomorrow_is_the_next_date(data, set_today):
    result = schedule_service.timetable(ASHA, "tomorrow")
    assert (result["day"], result["date"], codes(result["classes"])) == ("Tuesday", "2026-10-20", ["A503"])


def test_a_named_weekday_has_no_date(data, set_today):
    assert schedule_service.timetable(ASHA, "Monday")["date"] is None


def test_the_week_lists_each_teaching_day(data, set_today):
    week = schedule_service.timetable(ASHA, "week")["week"]
    assert [d["day"] for d in week] == ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    assert [len(d["classes"]) for d in week] == [2, 1, 0, 0, 0]


def test_a_weekend_has_no_classes_and_says_so(data, set_today):
    set_today(date(2026, 10, 17))
    result = schedule_service.timetable(ASHA)
    assert (result["day"], result["classes"], "error" in result) == ("Saturday", [], False)
    assert "weekend" in result["message"]


def test_an_empty_weekday_says_so(data, set_today):
    result = schedule_service.timetable(ASHA, "Wednesday")
    assert result["classes"] == [] and "No classes" in result["message"]


@pytest.mark.parametrize("word", ["funday", "m", "monthly", "mon day"])
def test_something_that_is_not_a_day_is_an_error(data, set_today, word):
    assert "is not a day" in schedule_service.timetable(ASHA, word)["error"]


@pytest.mark.parametrize("word", ["", "   ", None])
def test_a_blank_day_means_today(data, set_today, word):
    assert schedule_service.timetable(ASHA, word)["day"] == "Monday"


def test_only_the_students_own_section_and_semester_are_shown(data, set_today):
    everything = schedule_service.timetable(ASHA, "week")["week"]
    assert {c for d in everything for c in codes(d["classes"])} == {"A501", "A502", "A503"}
    assert "Classroom 5B" not in str(everything) and "B301" not in str(everything)


def test_each_student_gets_their_own_department(data, set_today):
    assert codes(schedule_service.timetable(RAVI)["classes"]) == ["C301"]


def test_a_student_with_no_section_is_told_why(db, set_today):
    from app.db.models import StudentProfile

    add_schedule_data(db)
    with db.begin() as session:
        session.get(StudentProfile, ASHA).section = None
    assert "section" in schedule_service.timetable(ASHA)["error"]


def test_a_student_with_no_profile_is_told_why(db, set_today):
    assert "section" in schedule_service.timetable(ASHA)["error"]


def test_an_unknown_student_is_an_error(data, set_today):
    assert schedule_service.timetable("9XX99XX999")["error"] == "No student record was found."


# --- exams


def test_the_exams_are_for_the_current_semester_in_date_order(data, set_today):
    result = schedule_service.exam_schedule(ASHA)
    assert result["semester"] == 5
    assert [(e["course_code"], e["date"]) for e in result["exams"]] == [
        ("A501", "2026-09-08"), ("A502", "2026-10-15"), ("A503", "2026-11-17"), ("A501", "2026-11-23"),
    ]


def test_each_exam_is_marked_past_today_or_upcoming(data, set_today):
    set_today(date(2026, 10, 15))
    by_course = {(e["course_code"], e["exam"]): e for e in schedule_service.exam_schedule(ASHA)["exams"]}
    assert by_course[("A501", "Internal Test 1")]["status"] == "past"
    assert by_course[("A501", "Internal Test 1")]["days_until"] is None
    assert (by_course[("A502", "End-Semester Examination")]["status"], by_course[("A502", "End-Semester Examination")]["days_until"]) == ("today", 0)
    end = by_course[("A501", "End-Semester Examination")]
    assert (end["status"], end["days_until"], end["weekday"]) == ("upcoming", 39, "Monday")


def test_an_exam_has_its_time_and_place(data, set_today):
    exam = next(e for e in schedule_service.exam_schedule(ASHA)["exams"] if e["course_code"] == "A503")
    assert exam == {
        "course_code": "A503", "course": "ML Lab", "exam": "Practical Examination", "type": "practical",
        "date": "2026-11-17", "weekday": "Tuesday", "start_time": "09:30", "duration_minutes": 180,
        "venue": "ISE Lab 1", "status": "upcoming", "days_until": 29,
    }


def test_other_departments_and_semesters_are_not_mixed_in(data, set_today):
    seen = {e["course_code"] for e in schedule_service.exam_schedule(ASHA)["exams"]}
    assert seen == {"A501", "A502", "A503"}
    assert {e["course_code"] for e in schedule_service.exam_schedule(RAVI)["exams"]} == {"C301"}


def test_another_semester_can_be_asked_for(data, set_today):
    result = schedule_service.exam_schedule(ASHA, 3)
    assert [e["course_code"] for e in result["exams"]] == ["B301"] and result["semester"] == 3


def test_a_semester_with_no_exams_says_so_without_an_error(data, set_today):
    result = schedule_service.exam_schedule(ASHA, 7)
    assert result["exams"] == [] and "No exam schedule" in result["message"] and "error" not in result


@pytest.mark.parametrize("semester", [0, 9, -1])
def test_a_semester_out_of_range_is_an_error(data, set_today, semester):
    assert "between 1 and 8" in schedule_service.exam_schedule(ASHA, semester)["error"]


def test_exams_for_an_unknown_student_are_an_error(data, set_today):
    assert "error" in schedule_service.exam_schedule("9XX99XX999")


# --- electives


def test_electives_are_those_of_the_students_department_and_semester(data):
    result = academic_service.elective_options(ASHA)
    assert result["semester"] == 5
    assert result["electives"] == [
        {"course_code": "A504", "name": "Cloud Computing", "credits": 3, "enrolled": True},
        {"course_code": "A505", "name": "Data Mining", "credits": 3, "enrolled": False},
    ]


def test_the_current_semester_comes_with_the_add_drop_rule(data):
    assert "first two weeks" in academic_service.elective_options(ASHA)["note"]


def test_another_semester_shows_nothing_as_enrolled_and_no_rule(data):
    result = academic_service.elective_options(ASHA, 7)
    assert result["electives"] == [{"course_code": "A701", "name": "Deep Learning", "credits": 3, "enrolled": False}]
    assert "note" not in result


def test_other_departments_electives_are_not_offered(data):
    assert academic_service.elective_options(RAVI)["electives"] == []
    assert "No electives" in academic_service.elective_options(RAVI)["message"]


def test_electives_for_a_bad_semester_or_student_are_an_error(data):
    assert "between 1 and 8" in academic_service.elective_options(ASHA, 12)["error"]
    assert "between 1 and 8" in academic_service.elective_options(ASHA, 0)["error"]
    assert "error" in academic_service.elective_options("9XX99XX999")


# --- fees


def term(result, name):
    return next(t for t in result["terms"] if t["term"] == name)


def test_a_term_before_its_deadline_is_upcoming(data, set_today):
    set_today(date(2026, 12, 1))
    even = term(fee_service.fee_dues(ASHA), "2026-27 even")
    assert (even["status"], even["days_until_due"], even["outstanding"]) == ("upcoming", 14, 68500)


def test_a_fully_paid_term_is_paid_with_nothing_unpaid(data, set_today):
    only = fee_service.fee_dues(RAVI)
    assert only["total_outstanding"] == 0 and only["terms"][0]["status"] == "paid"
    assert only["terms"][0]["unpaid_components"] == []


def test_a_partly_paid_term_lists_what_is_unpaid(data, set_today):
    set_today(date(2026, 7, 20))
    odd = term(fee_service.fee_dues(ASHA), "2026-27 odd")
    assert (odd["amount"], odd["paid"], odd["outstanding"]) == (68500, 62500, 6000)
    assert odd["unpaid_components"] == [{"component": "Laboratory Fee", "outstanding": 6000}]


@pytest.mark.parametrize(
    "day, late_fee",
    [("2026-07-16", 500), ("2026-07-22", 500), ("2026-07-23", 1000), ("2026-07-25", 1000)],
)
def test_inside_the_late_window_the_late_fee_is_500_a_week_or_part_of_one(data, set_today, day, late_fee):
    set_today(date.fromisoformat(day))
    odd = term(fee_service.fee_dues(ASHA), "2026-27 odd")
    assert (odd["status"], odd["late_fee"]) == ("overdue_in_late_window", late_fee)


def test_the_due_date_itself_is_not_late(data, set_today):
    set_today(date(2026, 7, 15))
    assert term(fee_service.fee_dues(ASHA), "2026-27 odd")["status"] == "upcoming"


def test_after_ten_days_the_late_window_has_closed_and_the_risk_is_stated(data, set_today):
    set_today(date(2026, 7, 26))
    result = fee_service.fee_dues(ASHA)
    odd = term(result, "2026-27 odd")
    assert (odd["status"], odd["days_overdue"], "late_fee" in odd) == ("overdue_beyond_late_window", 11, False)
    assert "barred" in result["note"] and result["overdue_outstanding"] == 6000


def test_totals_add_up_across_terms(data, set_today):
    set_today(date(2026, 10, 15))
    result = fee_service.fee_dues(ASHA)
    assert result["total_outstanding"] == 6000 + 68500 and result["overdue_outstanding"] == 6000
    assert result["currency"] == "INR"


def test_nothing_overdue_means_no_warning(data, set_today):
    set_today(date(2026, 12, 1))
    assert "note" not in fee_service.fee_dues(RAVI)


def test_students_never_see_each_others_fees(data, set_today):
    assert {t["term"] for t in fee_service.fee_dues(RAVI)["terms"]} == {"2026-27 odd"}


def test_no_records_and_unknown_students_are_distinguished(db, set_today):
    add_schedule_data(db)
    from app.db.models import FeeRecord
    from sqlalchemy import delete

    with db.begin() as session:
        session.execute(delete(FeeRecord))
    assert fee_service.fee_dues(ASHA)["message"] == "No fee records were found."
    assert fee_service.fee_dues("9XX99XX999")["error"] == "No student record was found."


# --- course information and the faculty directory


def test_a_course_has_its_instructor_and_hours(data):
    info = directory_service.course_info("A501")
    assert (info["name"], info["credits"], info["semester"], info["kind"]) == ("Machine Learning", 4, 5, "theory")
    assert info["instructor"] == {"faculty_id": "FAC-ISE-04", "name": "Dr. Farhan Sheikh", "designation": "Associate Professor"}
    assert info["weekly_hours"] == {"lecture": 3, "practical": 0}
    assert "handout" in info["note"]


@pytest.mark.parametrize("code", ["a501", " A501 ", "a501\n"])
def test_the_course_code_can_be_typed_loosely(data, code):
    assert directory_service.course_info(code)["course_code"] == "A501"


def test_a_course_without_a_teacher_yet_still_answers(data):
    info = directory_service.course_info("A502")
    assert info["instructor"] is None and info["weekly_hours"] is None and info["name"] == "Web Technologies"


def test_an_unknown_course_is_an_error(data):
    assert "ZZ999" in directory_service.course_info("zz999")["error"]


def test_faculty_are_found_by_full_name_in_any_case(data):
    assert directory_service.faculty_profile("dr. FARHAN sheikh")["faculty_id"] == "FAC-ISE-04"
    assert directory_service.faculty_profile("Farhan Sheikh")["name"] == "Dr. Farhan Sheikh"


def test_a_unique_surname_is_enough(data):
    assert directory_service.faculty_profile("Sheikh")["faculty_id"] == "FAC-ISE-04"


def test_faculty_are_found_by_id(data):
    assert directory_service.faculty_profile("fac-ise-04")["name"] == "Dr. Farhan Sheikh"


def test_the_profile_has_everything_a_student_would_ask_for(data):
    profile = directory_service.faculty_profile("Farhan Sheikh")
    assert profile == {
        "faculty_id": "FAC-ISE-04", "name": "Dr. Farhan Sheikh", "designation": "Associate Professor",
        "department": "ISE", "specialisation": "artificial intelligence and machine learning",
        "leadership_role": "Vice-Chair for Research", "office": "Main Academic Block, Room 217",
        "office_hours": "Wed 15:00-16:00", "email": "fac-ise-04@campus.example",
        "teaches": [{"course_code": "A501", "name": "Machine Learning"}, {"course_code": "A503", "name": "ML Lab"}],
    }


def test_a_shared_surname_asks_which_one_instead_of_guessing(data):
    result = directory_service.faculty_profile("Iyer")
    assert [m["name"] for m in result["matches"]] == ["Dr. Mohan Iyer", "Ms. Pooja Iyer"]
    assert "Ask which" in result["message"] and "email" not in result["matches"][0]


def test_a_full_name_picks_one_of_two_with_the_same_surname(data):
    assert directory_service.faculty_profile("Pooja Iyer")["faculty_id"] == "FAC-ISE-07"


def test_names_with_apostrophes_are_found(data):
    assert directory_service.faculty_profile("D'Souza")["faculty_id"] == "FAC-ISE-08"


def test_wildcards_are_not_wildcards(data):
    assert "error" in directory_service.faculty_profile("%")
    assert "error" in directory_service.faculty_profile("_")


def test_an_unknown_or_empty_name_is_an_error(data):
    assert "No faculty member" in directory_service.faculty_profile("Nobody Here")["error"]
    assert "error" in directory_service.faculty_profile("   ")
    assert "error" in directory_service.faculty_profile("Dr.")


def test_only_a_few_matches_are_listed(db):
    from app.db.models import FacultyMember

    with db.begin() as session:
        session.add_all(
            FacultyMember(faculty_id=f"F{i}", name=f"Dr. Same {i}", designation="Professor", department="ISE", email="x@y.z")
            for i in range(8)
        )
    result = directory_service.faculty_profile("Same")
    assert len(result["matches"]) == directory_service.MAX_MATCHES and "8 faculty" in result["message"]
