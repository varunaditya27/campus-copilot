"""Generate the academic seed data: courses.json, student_profiles.json and academic_records.json.

Run from the repository root:  python data/generate_academic_data.py

The output is committed, so nothing needs to run this unless the catalogue or
the roster changes. It is deterministic (a fixed random seed), so re-running it
reproduces the same files and a diff shows exactly what changed.

The data is invented for the demo university. Course names follow the subject
lists in knowledge/academics/curriculum-and-degree-structure.md. Grades and
attendance are generated per student, with a few deliberate cases so the
assistant has something real to say: one student with a backlog, and one with
an attendance figure in the condonation range described in the attendance policy.
"""

import json
import random
from pathlib import Path

DATA = Path(__file__).resolve().parent

# The odd semester is running, so a student in year Y is in semester 2Y - 1.
SEMESTER_OF_YEAR = {1: 1, 2: 3, 3: 5, 4: 7}

GRADE_POINTS = {"O": 10, "A+": 9, "A": 8, "B+": 7, "B": 6, "C": 5, "P": 4, "F": 0}

EVENT_CATEGORIES = [
    "artificial-intelligence",
    "web-development",
    "competitive-programming",
    "cybersecurity",
    "research",
    "robotics",
]
INTERESTS_BY_DEPARTMENT = {
    "IS": ["artificial-intelligence", "web-development", "competitive-programming"],
    "CS": ["competitive-programming", "cybersecurity", "artificial-intelligence"],
    "EC": ["robotics", "research", "cybersecurity"],
    "EE": ["robotics", "research", "artificial-intelligence"],
    "ME": ["robotics", "research", "competitive-programming"],
}

DEPARTMENTS = {
    "IS": "Information Science and Engineering",
    "CS": "Computer Science and Engineering",
    "EC": "Electronics and Communication Engineering",
    "EE": "Electrical and Electronics Engineering",
    "ME": "Mechanical Engineering",
}

# (course name, credits) for semesters 1-8 of each department. Names with
# "Lab", "Practice" are laboratories; "Project", "Capstone", "Internship" and
# "Seminar" are project work; "Elective" ones are electives.
CATALOGUE = {
    "IS": [
        [("Engineering Mathematics I", 4), ("Engineering Physics", 3), ("Programming Fundamentals", 3), ("Technical Communication", 2), ("Digital Logic", 3), ("Programming Lab", 1)],
        [("Engineering Mathematics II", 4), ("Discrete Mathematics", 3), ("Data Structures", 4), ("Engineering Chemistry", 3), ("Environmental Studies", 2), ("Data Structures Lab", 1)],
        [("Object-Oriented Programming", 4), ("Database Management Systems", 4), ("Operating Systems", 4), ("Probability and Statistics", 3), ("DBMS Lab", 1), ("OOP Lab", 1)],
        [("Computer Networks", 4), ("Design and Analysis of Algorithms", 4), ("Software Engineering Fundamentals", 3), ("Theory of Computation", 3), ("Operating Systems Lab", 1), ("Networks Lab", 1)],
        [("Machine Learning", 4), ("Web Technologies", 3), ("Software Engineering", 3), ("Cloud Computing", 3), ("Program Elective I", 3), ("Machine Learning Lab", 1)],
        [("Information Systems Design", 4), ("Data Mining", 3), ("Information Security", 3), ("Program Elective II", 3), ("Open Elective I", 3), ("Mini Project", 2)],
        [("Big Data Analytics", 4), ("Deep Learning", 4), ("Program Elective III", 3), ("Program Elective IV", 3), ("Capstone Project Phase I", 4), ("Internship", 2)],
        [("Program Elective V", 3), ("Open Elective II", 3), ("Professional Ethics", 2), ("Capstone Project Phase II", 8)],
    ],
    "CS": [
        [("Engineering Mathematics I", 4), ("Engineering Physics", 3), ("Programming Fundamentals", 3), ("Technical Communication", 2), ("Digital Design", 3), ("Programming Lab", 1)],
        [("Engineering Mathematics II", 4), ("Discrete Mathematics", 3), ("Data Structures", 4), ("Engineering Chemistry", 3), ("Environmental Studies", 2), ("Data Structures Lab", 1)],
        [("Computer Organization", 4), ("Database Systems", 4), ("Operating Systems", 4), ("Probability and Statistics", 3), ("Database Lab", 1), ("Operating Systems Lab", 1)],
        [("Theory of Computation", 4), ("Algorithms", 4), ("Object-Oriented Design", 3), ("Linear Algebra", 3), ("Algorithms Lab", 1), ("Software Lab", 1)],
        [("Compiler Design", 4), ("Artificial Intelligence", 4), ("Computer Networks", 4), ("Program Elective I", 3), ("Compiler Lab", 1), ("Networks Lab", 1)],
        [("Distributed Systems", 4), ("Machine Learning", 3), ("Information Security", 3), ("Program Elective II", 3), ("Open Elective I", 3), ("Mini Project", 2)],
        [("Program Elective III", 3), ("Program Elective IV", 3), ("Program Elective V", 3), ("Open Elective II", 3), ("Capstone Project Phase I", 4), ("Internship", 2)],
        [("Program Elective VI", 3), ("Professional Ethics", 2), ("Seminar", 2), ("Capstone Project Phase II", 8)],
    ],
    "EC": [
        [("Engineering Mathematics I", 4), ("Engineering Physics", 3), ("Basic Electronics", 3), ("Programming for Engineers", 3), ("Technical Communication", 2), ("Electronics Lab", 1)],
        [("Engineering Mathematics II", 4), ("Circuit Theory", 4), ("Engineering Chemistry", 3), ("Signals and Systems", 3), ("Environmental Studies", 2), ("Circuits Lab", 1)],
        [("Analog Electronics", 4), ("Digital Signal Processing", 4), ("Electromagnetic Theory", 4), ("Probability and Random Processes", 3), ("Analog Lab", 1), ("DSP Lab", 1)],
        [("Communication Systems", 4), ("Digital System Design", 3), ("Microprocessors", 3), ("Control Systems", 3), ("Communication Lab", 1), ("Microprocessors Lab", 1)],
        [("Embedded Systems", 4), ("VLSI Design", 4), ("Microcontrollers", 3), ("Wireless Communication", 3), ("Embedded Lab", 1), ("VLSI Lab", 1)],
        [("Antennas and Propagation", 3), ("Information Theory", 3), ("Program Elective I", 3), ("Open Elective I", 3), ("Wireless Lab", 1), ("Mini Project", 2)],
        [("RF Systems", 4), ("IoT and Embedded Systems", 3), ("Program Elective II", 3), ("Program Elective III", 3), ("Capstone Project Phase I", 4), ("Internship", 2)],
        [("Program Elective IV", 3), ("Professional Ethics", 2), ("Open Elective II", 3), ("Capstone Project Phase II", 8)],
    ],
    "EE": [
        [("Engineering Mathematics I", 4), ("Engineering Physics", 3), ("Circuit Analysis", 4), ("Basic Electrical Machines", 3), ("Technical Communication", 2), ("Electrical Lab", 1)],
        [("Engineering Mathematics II", 4), ("Electromagnetic Fields", 4), ("Engineering Chemistry", 3), ("Programming for Engineers", 3), ("Environmental Studies", 2), ("Circuits Lab", 1)],
        [("Power Systems", 4), ("Control Systems", 4), ("Power Electronics", 4), ("Electrical Machines", 4), ("Machines Lab", 1), ("Control Lab", 1)],
        [("Analog Electronics", 3), ("Digital Electronics", 3), ("Measurements and Instrumentation", 3), ("Electrical Machines II", 4), ("Electronics Lab", 1), ("Instrumentation Lab", 1)],
        [("Industrial Automation", 4), ("Renewable Energy Systems", 3), ("Instrumentation", 3), ("Power System Protection", 3), ("Automation Lab", 1), ("Power Systems Lab", 1)],
        [("Power System Analysis", 4), ("Embedded Control", 3), ("Program Elective I", 3), ("Open Elective I", 3), ("Simulation Lab", 1), ("Mini Project", 2)],
        [("Smart Grids", 4), ("Program Elective II", 3), ("Program Elective III", 3), ("Capstone Project Phase I", 4), ("Internship", 2)],
        [("Program Elective IV", 3), ("Professional Ethics", 2), ("Open Elective II", 3), ("Capstone Project Phase II", 8)],
    ],
    "ME": [
        [("Engineering Mathematics I", 4), ("Engineering Physics", 3), ("Engineering Mechanics", 4), ("Engineering Graphics", 3), ("Technical Communication", 2), ("Workshop Practice", 1)],
        [("Engineering Mathematics II", 4), ("Thermodynamics", 4), ("Materials Science", 3), ("Engineering Chemistry", 3), ("Environmental Studies", 2), ("Graphics Lab", 1)],
        [("Fluid Mechanics", 4), ("Manufacturing Processes", 3), ("Machine Design", 4), ("Kinematics of Machines", 4), ("Manufacturing Lab", 1), ("Fluid Mechanics Lab", 1)],
        [("Dynamics of Machines", 4), ("Applied Thermodynamics", 4), ("Metrology", 3), ("Mechanics of Materials", 3), ("Thermal Lab", 1), ("Materials Lab", 1)],
        [("Heat Transfer", 4), ("CAD/CAM", 3), ("Industrial Engineering", 3), ("Automation and Robotics", 3), ("Heat Transfer Lab", 1), ("CAD Lab", 1)],
        [("Design of Machine Elements", 4), ("Mechatronics", 3), ("Program Elective I", 3), ("Open Elective I", 3), ("CAM Lab", 1), ("Mini Project", 2)],
        [("Advanced Manufacturing", 4), ("Program Elective II", 3), ("Program Elective III", 3), ("Capstone Project Phase I", 4), ("Internship", 2)],
        [("Program Elective IV", 3), ("Professional Ethics", 2), ("Open Elective II", 3), ("Capstone Project Phase II", 8)],
    ],
}


def kind_of(name: str) -> str:
    if name.endswith(("Lab", "Practice")):
        return "lab"
    if any(word in name for word in ("Project", "Capstone", "Internship", "Seminar")):
        return "project"
    if "Elective" in name:
        return "elective"
    return "theory"


# Classes held so far in the running semester, and over a whole one.
HELD_SO_FAR = {"theory": (24, 28), "lab": (6, 8), "project": (5, 5), "elective": (24, 28)}
WHOLE_SEMESTER = {"theory": (40, 42), "lab": (12, 12), "project": (10, 10), "elective": (40, 42)}


def build_courses() -> list[dict]:
    courses = []
    for code, rows in CATALOGUE.items():
        for semester, subjects in enumerate(rows, start=1):
            for index, (name, credits) in enumerate(subjects, start=1):
                courses.append(
                    {
                        "course_code": f"{code}{semester}{index:02d}",
                        "name": name,
                        "credits": credits,
                        "department": DEPARTMENTS[code],
                        "semester": semester,
                        "kind": kind_of(name),
                    }
                )
    return courses


def letter_for(score: float) -> str:
    for threshold, letter in ((9.5, "O"), (8.5, "A+"), (7.5, "A"), (6.5, "B+"), (5.5, "B"), (4.5, "C"), (3.5, "P")):
        if score >= threshold:
            return letter
    return "F"


def attended_share(rng: random.Random, ability: float) -> float:
    return min(0.99, max(0.74, 0.80 + 0.17 * ability + rng.uniform(-0.07, 0.04)))


def build_students_data(courses: list[dict]) -> tuple[list[dict], list[dict]]:
    rng = random.Random(2026)
    students = json.loads((DATA / "students.json").read_text())
    by_department_semester: dict[tuple[str, int], list[dict]] = {}
    for course in courses:
        by_department_semester.setdefault((course["department"], course["semester"]), []).append(course)

    profiles, records = [], []
    for student in sorted(students, key=lambda s: s["student_id"]):
        code = student["student_id"][5:7]
        department = DEPARTMENTS[code]
        semester = SEMESTER_OF_YEAR[student["year"]]
        ability = rng.uniform(0.35, 0.95)

        elective_codes = [
            c["course_code"]
            for c in by_department_semester.get((department, semester), [])
            if c["kind"] == "elective"
        ]
        interests = rng.sample(INTERESTS_BY_DEPARTMENT[code], k=2)
        profiles.append(
            {
                "student_id": student["student_id"],
                "semester": semester,
                "section": "AB"[rng.randrange(2)],
                "electives": elective_codes,
                "preferences": {"interests": [c for c in EVENT_CATEGORIES if c in interests]},
            }
        )

        for done in range(1, semester):
            for course in by_department_semester[(department, done)]:
                score = ability * 10 + rng.gauss(0, 1.1)
                total = rng.randint(*WHOLE_SEMESTER[course["kind"]])
                records.append(
                    {
                        "student_id": student["student_id"],
                        "course_code": course["course_code"],
                        "semester": done,
                        "attended": round(total * attended_share(rng, ability)),
                        "total": total,
                        "grade": letter_for(max(score, 3.6)),  # a backlog is added on purpose below
                    }
                )
        for course in by_department_semester[(department, semester)]:
            total = rng.randint(*HELD_SO_FAR[course["kind"]])
            records.append(
                {
                    "student_id": student["student_id"],
                    "course_code": course["course_code"],
                    "semester": semester,
                    "attended": round(total * attended_share(rng, ability)),
                    "total": total,
                    "grade": None,
                }
            )
    return profiles, records


def add_deliberate_cases(records: list[dict]) -> None:
    def record(student_id: str, course_code: str) -> dict:
        return next(r for r in records if r["student_id"] == student_id and r["course_code"] == course_code)

    # Aarav (ISE, semester 5): Machine Learning attendance of 72%, inside the
    # 65-74% range where condonation can be applied for.
    ml = record("1RV23IS101", "IS501")
    ml["attended"], ml["total"] = 18, 25
    # ...and a second subject just under the 75% line, and one comfortably fine.
    web = record("1RV23IS101", "IS502")
    web["attended"], web["total"] = 27, 28
    cloud = record("1RV23IS101", "IS504")
    cloud["attended"], cloud["total"] = 20, 27

    # Arjun (CSE, semester 7) carries one backlog from semester 2.
    record("1RV22CS220", "CS203")["grade"] = "F"
    # Aditya (ECE, semester 7) is below the 65% line in one subject.
    below_the_line = record("1RV22EC088", "EC705")
    below_the_line["attended"], below_the_line["total"] = 15, 26


def main() -> None:
    courses = build_courses()
    profiles, records = build_students_data(courses)
    add_deliberate_cases(records)

    (DATA / "courses.json").write_text(json.dumps(courses, indent=2, ensure_ascii=False) + "\n")
    (DATA / "student_profiles.json").write_text(json.dumps(profiles, indent=2, ensure_ascii=False) + "\n")
    (DATA / "academic_records.json").write_text(json.dumps(records, indent=2, ensure_ascii=False) + "\n")
    print(f"{len(courses)} courses, {len(profiles)} profiles, {len(records)} academic records")


if __name__ == "__main__":
    main()
