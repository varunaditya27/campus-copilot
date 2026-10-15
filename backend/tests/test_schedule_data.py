"""The committed demo data: that the generator still produces it, and that it follows
the rules the knowledge documents state."""
import importlib.util
import json
from collections import Counter, defaultdict
from datetime import date

import pytest
from alembic import command
from sqlalchemy.orm import sessionmaker

from app.core import clock
from app.core.config import DATA_DIR
from app.db import session as db_session
from app.db.seed import seed
from app.services import academic_service, directory_service, entity_service, fee_service, schedule_service
from test_db_setup import _alembic_config, _migrated_engine  # noqa: F401


def load(name):
    return json.loads((DATA_DIR / f"{name}.json").read_text())


@pytest.fixture(scope="module")
def generator():
    spec = importlib.util.spec_from_file_location("generate_schedule_data", DATA_DIR / "generate_schedule_data.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


courses = load("courses")
COURSE = {c["course_code"]: c for c in courses}


# --- the committed files are what the generator makes


def test_the_committed_files_match_the_generator(generator):
    faculty = generator.parse_faculty()
    assert faculty == load("faculty_members")
    assert generator.build_offerings(courses, faculty) == load("course_offerings")
    assert generator.build_timetable(courses) == load("timetable_slots")
    assert generator.build_exams(courses) == load("exams")
    assert generator.build_fees() == load("fee_records")


# --- faculty


def test_the_directory_is_exactly_the_people_in_the_knowledge_documents():
    in_documents = set(entity_service.faculty_names().values())
    assert {f["name"] for f in load("faculty_members")} == in_documents and len(in_documents) == 35


def test_each_department_has_one_head_and_seven_people():
    faculty = load("faculty_members")
    assert set(Counter(f["department"] for f in faculty).values()) == {7} and len({f["department"] for f in faculty}) == 5
    heads = [f for f in faculty if f["leadership_role"] == "Head of Department"]
    assert len(heads) == 5 and len({h["department"] for h in heads}) == 5
    assert sum((f["leadership_role"] or "").startswith("Vice-Chair") for f in faculty) == 10


def test_what_the_documents_say_is_kept_exactly():
    by_name = {f["name"]: f for f in load("faculty_members")}
    sheikh = by_name["Dr. Farhan Sheikh"]
    assert (sheikh["designation"], sheikh["specialisation"], sheikh["leadership_role"]) == (
        "Associate Professor", "artificial intelligence and machine learning", "Vice-Chair for Research",
    )
    assert by_name["Dr. Suresh Krishnan"]["specialisation"] == "distributed systems"
    assert by_name["Dr. Radhika Venkatesh"]["office"] == "Main Academic Block, Room 214"  # the department office
    assert by_name["Dr. Suresh Krishnan"]["office"] == "Main Academic Block, Room 226"


def test_faculty_ids_emails_and_offices_are_unique():
    faculty = load("faculty_members")
    for field in ("faculty_id", "email", "office"):
        assert len({f[field] for f in faculty}) == len(faculty), field
    assert next(f for f in faculty if "D'Souza" in f["name"])["email"] == "shalini.dsouza@campus.example"


def test_every_course_has_a_teacher_from_its_own_department():
    faculty = {f["faculty_id"]: f for f in load("faculty_members")}
    offerings = load("course_offerings")
    assert {o["course_code"] for o in offerings} == set(COURSE)
    assert all(faculty[o["faculty_id"]]["department"] == COURSE[o["course_code"]]["department"] for o in offerings)


# --- timetable


def slot_minutes(slot):
    h1, m1 = map(int, slot["start"].split(":"))
    h2, m2 = map(int, slot["end"].split(":"))
    return (h2 * 60 + m2) - (h1 * 60 + m1)


def test_a_class_group_is_never_double_booked():
    by_group_day = defaultdict(list)
    for s in load("timetable_slots"):
        by_group_day[(s["department"], s["semester"], s["section"], s["day"])].append((s["start"], s["end"]))
    for key, spans in by_group_day.items():
        spans.sort()
        assert all(a[1] <= b[0] for a, b in zip(spans, spans[1:])), key


def test_nothing_is_taught_at_the_weekend_or_over_lunch():
    for s in load("timetable_slots"):
        assert s["day"] in range(5)
        assert not (s["start"] < "14:00" < s["end"]) and not (s["start"] < "13:15" < s["end"]), s
        assert s["start"] >= "09:00" and s["end"] <= "17:00"


def test_every_course_gets_the_contact_hours_it_declares_in_both_sections():
    offerings = {o["course_code"]: o for o in load("course_offerings")}
    minutes = defaultdict(int)
    for s in load("timetable_slots"):
        minutes[(s["department"], s["semester"], s["section"], s["course_code"])] += slot_minutes(s)
    for course in courses:
        if course["semester"] % 2 == 0:
            continue
        offering = offerings[course["course_code"]]
        for section in "AB":
            key = (course["department"], course["semester"], section, course["course_code"])
            assert minutes[key] == 60 * (offering["lecture_hours"] + offering["practical_hours"]), key


def test_only_the_running_odd_semesters_are_scheduled():
    assert {s["semester"] for s in load("timetable_slots")} == {1, 3, 5, 7}


# --- exams


def test_every_theory_course_has_two_internal_tests_and_an_end_semester_exam():
    exams = defaultdict(list)
    for e in load("exams"):
        exams[e["course_code"]].append(e["name"])
    for course in courses:
        if course["semester"] % 2 == 0:
            assert course["course_code"] not in exams
        elif course["kind"] in ("theory", "elective"):
            assert sorted(exams[course["course_code"]]) == ["End-Semester Examination", "Internal Test 1", "Internal Test 2"]
        elif course["kind"] == "lab":
            assert exams[course["course_code"]] == ["Practical Examination"]
        else:
            assert exams[course["course_code"]] == ["Project Final Evaluation"]


def test_a_student_never_has_two_exams_of_a_kind_on_one_day():
    seen = Counter()
    for e in load("exams"):
        course = COURSE[e["course_code"]]
        seen[(course["department"], course["semester"], e["name"], e["date"])] += 1
    assert max(seen.values()) == 1


def test_exams_fall_on_weekdays_in_the_expected_order():
    for e in load("exams"):
        assert date.fromisoformat(e["date"]).weekday() < 5
    by_name = defaultdict(list)
    for e in load("exams"):
        by_name[e["name"]].append(e["date"])
    assert max(by_name["Internal Test 1"]) < min(by_name["Internal Test 2"]) < min(by_name["Practical Examination"]) <= min(by_name["End-Semester Examination"]) < min(by_name["Project Final Evaluation"])


# --- fees follow the published structure


def test_the_yearly_fee_matches_the_fee_structure():
    per_year = defaultdict(int)
    for r in load("fee_records"):
        per_year[r["student_id"]] += r["amount"]
    for student_id, total in per_year.items():
        code = student_id[5:7]
        assert total == 163500 + (2000 if code in ("EC", "ME") else 0), student_id


def test_every_student_has_every_component_in_both_terms_with_the_published_due_dates():
    records = load("fee_records")
    assert len(records) == 20 * 2 * 5
    assert {(r["term"], r["due_date"]) for r in records} == {("2026-27 odd", "2026-07-15"), ("2026-27 even", "2026-12-15")}
    assert all(0 <= r["paid_amount"] <= r["amount"] for r in records)
    assert all((r["paid_on"] is None) == (r["paid_amount"] == 0) for r in records)


# --- against a real, seeded database


@pytest.fixture
def real(tmp_path, monkeypatch):
    engine, _ = _migrated_engine(tmp_path)
    factory = sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(db_session, "SessionLocal", factory)
    monkeypatch.setattr(clock, "today", lambda: date(2026, 10, 15))
    with factory() as session:
        seed(session)
    yield
    engine.dispose()


def test_aarav_has_a_full_week_that_matches_his_courses(real):
    week = schedule_service.timetable("1RV23IS101", "week")["week"]
    taught = {c["course_code"] for d in week for c in d["classes"]}
    assert taught == {c["course_code"] for c in courses if c["department"].startswith("Information") and c["semester"] == 5}
    assert all(c["room"] for d in week for c in d["classes"])


def test_aarav_sees_his_own_exams_and_electives_and_a_clean_fee_record(real):
    exams = schedule_service.exam_schedule("1RV23IS101")["exams"]
    assert {e["status"] for e in exams} == {"past", "upcoming"}
    assert sum(e["type"] == "end-semester" for e in exams) >= 4
    expected = [c["course_code"] for c in courses if c["department"].startswith("Information") and c["semester"] == 5 and c["kind"] == "elective"]
    options = academic_service.elective_options("1RV23IS101")["electives"]
    assert [o["course_code"] for o in options] == expected and expected and all(o["enrolled"] for o in options)
    assert fee_service.fee_dues("1RV23IS101")["overdue_outstanding"] == 0


def test_ananyas_unpaid_lab_fee_is_past_the_late_window(real):
    dues = fee_service.fee_dues("1RV24IS219")
    odd = next(t for t in dues["terms"] if t["term"] == "2026-27 odd")
    assert (odd["status"], odd["outstanding"], odd["unpaid_components"]) == (
        "overdue_beyond_late_window", 6000, [{"component": "Laboratory Fee", "outstanding": 6000}]
    )
    assert "barred" in dues["note"]


def test_adityas_part_payment_is_shown(real):
    odd = next(t for t in fee_service.fee_dues("1RV22EC088")["terms"] if t["term"] == "2026-27 odd")
    assert odd["unpaid_components"] == [{"component": "Tuition Fee", "outstanding": 22500}]


def test_priyas_early_payment_shows_the_next_term_as_paid(real):
    even = next(t for t in fee_service.fee_dues("1RV22IS305")["terms"] if t["term"] == "2026-27 even")
    assert even["status"] == "paid"


def test_the_directory_answers_about_a_real_person_and_course(real):
    person = directory_service.faculty_profile("Farhan Sheikh")
    assert person["designation"] == "Associate Professor" and person["teaches"]
    first = person["teaches"][0]["course_code"]
    assert directory_service.course_info(first)["instructor"]["name"] == "Dr. Farhan Sheikh"
    assert "matches" in directory_service.faculty_profile("Menon")
