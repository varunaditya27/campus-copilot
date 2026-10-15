"""Generate the faculty directory, course teaching details, class timetable, exam
schedule and fee records: faculty_members.json, course_offerings.json,
timetable_slots.json, exams.json and fee_records.json.

Run from the repository root (after generate_academic_data.py):
    python data/generate_schedule_data.py

The output is committed. It is deterministic (a fixed random seed), so
re-running reproduces the same files and a diff shows exactly what changed.

Everything here is invented for the demo university, except what is read from
the knowledge documents: the faculty names, designations, specialisations,
leadership roles and department office rooms come from
knowledge/campus/faculty-and-departments-directory.md, and the fee amounts and
due dates follow knowledge/administration/admissions-and-fee-structure.md.
Invented: each person's office room, office hours and email address, who teaches
which course, the weekly timetable, and all exam dates and venues.

The timetable keeps each class group (department, semester, section) free of
clashes. It does not check that a teacher is in only one place at a time: a
department has about seven faculty and far more weekly teaching hours than that.
"""

import json
import random
import re
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

DATA = Path(__file__).resolve().parent
ROOT = DATA.parent

CODES = {
    "Information Science and Engineering": "IS",
    "Computer Science and Engineering": "CS",
    "Electronics and Communication Engineering": "EC",
    "Electrical and Electronics Engineering": "EE",
    "Mechanical Engineering": "ME",
}
ODD_SEMESTERS = (1, 3, 5, 7)
SECTIONS = ("A", "B")

# One lesson each; the break and lunch sit between 11:00-11:15 and 13:15-14:00.
PERIODS = [
    ("09:00", "10:00"),
    ("10:00", "11:00"),
    ("11:15", "12:15"),
    ("12:15", "13:15"),
    ("14:00", "15:00"),
    ("15:00", "16:00"),
    ("16:00", "17:00"),
]
# A two-hour block (a lab or project session) may not straddle a break.
BLOCKS = [(0, 1), (2, 3), (4, 5), (5, 6)]
DAYS = 5  # Monday to Friday

# Calendar for the running odd semester, as dates in ISO form.
INTERNAL_1 = date(2026, 9, 7)
INTERNAL_2 = date(2026, 10, 26)
PRACTICALS = date(2026, 11, 16)
END_SEMESTER = date(2026, 11, 23)
PROJECT_REVIEWS = date(2026, 12, 7)

# Half of the annual fee structure, one instalment per semester.
FEES_PER_SEMESTER = {
    "Tuition Fee": 62500,
    "Development Fee": 9000,
    "Examination Fee": 3000,
    "Laboratory Fee": 6000,
    "Student Activity Fee": 1250,
}
LAB_SUPPLEMENT = {"EC": 1000, "ME": 1000}  # the 2,000 a year consumables supplement
ODD_TERM, EVEN_TERM = "2026-27 odd", "2026-27 even"
ODD_DUE, EVEN_DUE = "2026-07-15", "2026-12-15"


def parse_faculty() -> list[dict]:
    text = (ROOT / "knowledge/campus/faculty-and-departments-directory.md").read_text()
    rng = random.Random(2027)
    faculty = []
    for department, code in CODES.items():
        section = re.search(rf"^## {re.escape(department)}\n(.*?)(?=^## )", text, re.S | re.M).group(1)
        office_room = int(re.search(r"Room (\d+)", section).group(1))
        floor_word = "Main Academic Block"

        people = []
        hod = re.search(
            r"Head of Department: ((?:Dr|Prof|Mr|Ms)\. [^,]+), ([A-Za-z ]+?)(?:, specializing in ([^.]+))?\.", section
        )
        people.append((hod.group(1), hod.group(2), hod.group(3), "Head of Department"))
        for name, details in re.findall(r"((?:Dr|Prof|Mr|Ms)\. [A-Z][A-Za-z' ]+?) \(([^)]+)\)", section):
            designation, *rest = [part.strip() for part in details.split(",")]
            role = next((re.sub(r"^also ", "", p) for p in rest if "Vice-Chair" in p), None)
            specialisation = ", ".join(p for p in rest if "Vice-Chair" not in p) or None
            people.append((name, designation, specialisation, role))

        for index, (name, designation, specialisation, role) in enumerate(people, start=1):
            first_last = re.sub(r"^(?:Dr|Prof|Mr|Ms)\. ", "", name).lower().replace("'", "").split()
            days = rng.sample(["Mon", "Tue", "Wed", "Thu", "Fri"], 2)
            windows = rng.sample(["11:00-12:00", "14:00-15:00", "15:00-16:00"], 2)
            faculty.append(
                {
                    "faculty_id": f"FAC-{code}-{index:02d}",
                    "name": name,
                    "designation": designation,
                    "department": department,
                    "specialisation": specialisation,
                    "leadership_role": role,
                    "office": f"{floor_word}, Room {office_room if index == 1 else office_room + index - 1}",
                    "office_hours": f"{days[0]} {windows[0]}, {days[1]} {windows[1]}",
                    "email": f"{'.'.join(first_last)}@campus.example",
                }
            )
    return faculty


def lecture_hours(course: dict) -> int:
    if course["kind"] in ("lab", "project"):
        return 0
    return 3 if course["credits"] >= 3 or course["kind"] == "elective" else 2


def build_offerings(courses: list[dict], faculty: list[dict]) -> list[dict]:
    by_department = defaultdict(list)
    for person in faculty:
        by_department[person["department"]].append(person["faculty_id"])
    next_teacher: dict[str, int] = defaultdict(int)
    offerings = []
    for course in courses:
        pool = by_department[course["department"]]
        teacher = pool[next_teacher[course["department"]] % len(pool)]
        next_teacher[course["department"]] += 1
        offerings.append(
            {
                "course_code": course["course_code"],
                "faculty_id": teacher,
                "lecture_hours": lecture_hours(course),
                "practical_hours": 2 if course["kind"] in ("lab", "project") else 0,
            }
        )
    return offerings


def build_timetable(courses: list[dict]) -> list[dict]:
    slots = []
    for department, code in CODES.items():
        for semester in ODD_SEMESTERS:
            group = sorted(
                (c for c in courses if c["department"] == department and c["semester"] == semester),
                key=lambda c: (c["kind"] not in ("lab", "project"), c["course_code"]),  # long blocks first
            )
            for section in SECTIONS:
                taken: set[tuple[int, int]] = set()
                load = [0] * DAYS
                shift = SECTIONS.index(section)
                for index, course in enumerate(group):
                    room = f"Classroom {code}-{semester}{section}"
                    if course["kind"] == "lab":
                        room = f"{code} Lab {index % 3 + 1}"
                    elif course["kind"] == "project":
                        room = f"{code} Project Lab"
                    placed: list[tuple[int, tuple[int, ...]]] = []
                    if course["kind"] in ("lab", "project"):
                        choices = [(d, b) for d in range(DAYS) for b in BLOCKS[2:]]  # afternoons
                        order = sorted(choices, key=lambda db: (load[db[0]], (db[0] + index + shift) % DAYS, db[1]))
                        day, block = next(
                            (d, b) for d, b in order if not any((d, p) in taken for p in b)
                        )
                        placed.append((day, block))
                    else:
                        used_days: set[int] = set()
                        for _ in range(lecture_hours(course)):
                            days = sorted(
                                range(DAYS),
                                key=lambda d: (d in used_days, load[d], (d + index + shift) % DAYS),
                            )
                            day, period = next(
                                (d, p) for d in days for p in range(len(PERIODS)) if (d, p) not in taken
                            )
                            used_days.add(day)
                            placed.append((day, (period,)))
                            taken.add((day, period))
                            load[day] += 1
                    for day, periods in placed:
                        taken.update((day, p) for p in periods)
                        if len(periods) > 1:
                            load[day] += len(periods)
                        slots.append(
                            {
                                "department": department,
                                "semester": semester,
                                "section": section,
                                "day": day,
                                "start": PERIODS[periods[0]][0],
                                "end": PERIODS[periods[-1]][1],
                                "course_code": course["course_code"],
                                "room": room,
                            }
                        )
    return slots


def working_days(start: date):
    day = start
    while True:
        if day.weekday() < 5:
            yield day
        day += timedelta(days=1)


def build_exams(courses: list[dict]) -> list[dict]:
    exams = []
    for department, code in CODES.items():
        for semester in ODD_SEMESTERS:
            group = sorted(
                (c for c in courses if c["department"] == department and c["semester"] == semester),
                key=lambda c: c["course_code"],
            )
            theory = [c for c in group if c["kind"] in ("theory", "elective")]
            labs = [c for c in group if c["kind"] == "lab"]
            projects = [c for c in group if c["kind"] == "project"]
            # At most one exam per day for a class group, as the calendar requires.
            for label, start, hour, minutes in (
                ("Internal Test 1", INTERNAL_1, "14:00", 90),
                ("Internal Test 2", INTERNAL_2, "14:00", 90),
            ):
                for course, day in zip(theory, working_days(start)):
                    exams.append(_exam(course, label, "internal", day, hour, minutes, "Regular classroom"))
            for course, day in zip(theory, working_days(END_SEMESTER)):
                hall = f"Examination Hall {(semester // 2 + list(CODES.values()).index(code)) % 4 + 1}"
                exams.append(_exam(course, "End-Semester Examination", "end-semester", day, "09:30", 180, hall))
            for course, day in zip(labs, working_days(PRACTICALS)):
                exams.append(_exam(course, "Practical Examination", "practical", day, "09:30", 180, f"{code} Lab 1"))
            for course, day in zip(projects, working_days(PROJECT_REVIEWS)):
                exams.append(_exam(course, "Project Final Evaluation", "project-review", day, "10:00", 60, f"{code} Project Lab"))
            assert len(theory) <= 10 and len(labs) <= 5, (department, semester)
    return exams


def _exam(course: dict, name: str, kind: str, day: date, start: str, minutes: int, venue: str) -> dict:
    return {
        "course_code": course["course_code"],
        "name": name,
        "exam_type": kind,
        "date": day.isoformat(),
        "start_time": start,
        "duration_minutes": minutes,
        "venue": venue,
    }


def build_fees() -> list[dict]:
    rng = random.Random(2028)
    students = json.loads((DATA / "students.json").read_text())
    records = []
    for student in sorted(students, key=lambda s: s["student_id"]):
        code = student["student_id"][5:7]
        for term, due in ((ODD_TERM, ODD_DUE), (EVEN_TERM, EVEN_DUE)):
            for component, amount in FEES_PER_SEMESTER.items():
                if component == "Laboratory Fee":
                    amount += LAB_SUPPLEMENT.get(code, 0)
                paid = term == ODD_TERM
                records.append(
                    {
                        "student_id": student["student_id"],
                        "term": term,
                        "component": component,
                        "amount": amount,
                        "due_date": due,
                        "paid_amount": amount if paid else 0,
                        "paid_on": date(2026, 7, rng.randint(1, 15)).isoformat() if paid else None,
                    }
                )

    def record(student_id: str, term: str, component: str) -> dict:
        return next(
            r for r in records if (r["student_id"], r["term"], r["component"]) == (student_id, term, component)
        )

    # Ananya never paid the odd semester's laboratory fee: past the late-payment window.
    lab = record("1RV24IS219", ODD_TERM, "Laboratory Fee")
    lab["paid_amount"], lab["paid_on"] = 0, None
    # Aditya paid part of the odd semester's tuition.
    tuition = record("1RV22EC088", ODD_TERM, "Tuition Fee")
    tuition["paid_amount"] = 40000
    # Priya paid the even semester early, in full.
    for component in FEES_PER_SEMESTER:
        early = record("1RV22IS305", EVEN_TERM, component)
        early["paid_amount"], early["paid_on"] = early["amount"], "2026-09-30"
    return records


def main() -> None:
    courses = json.loads((DATA / "courses.json").read_text())
    faculty = parse_faculty()
    outputs = {
        "faculty_members.json": faculty,
        "course_offerings.json": build_offerings(courses, faculty),
        "timetable_slots.json": build_timetable(courses),
        "exams.json": build_exams(courses),
        "fee_records.json": build_fees(),
    }
    for filename, rows in outputs.items():
        (DATA / filename).write_text(json.dumps(rows, indent=2, ensure_ascii=False) + "\n")
    print(", ".join(f"{len(rows)} {name.removesuffix('.json')}" for name, rows in outputs.items()))


if __name__ == "__main__":
    main()
