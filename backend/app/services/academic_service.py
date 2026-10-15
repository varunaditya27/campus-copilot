import math

from sqlalchemy import select

from app.db import session as db_session
from app.db.models import AcademicRecord, Course, Student, StudentProfile
from app.models.academic import ElectiveInfo, Preferences, StudentProfileView

# From the attendance policy: 75% is needed to sit the end-semester exam; between
# 65% and 74% a student may apply for condonation; below 65% they are debarred.
ATTENDANCE_REQUIRED = 75.0
CONDONATION_FLOOR = 65.0

# From the grading policy.
GRADE_POINTS = {"O": 10, "A+": 9, "A": 8, "B+": 7, "B": 6, "C": 5, "P": 4, "F": 0}


def default_semester(year: int) -> int:
    """The odd semester is the one running, so a student in year Y is in semester 2Y - 1."""
    return 2 * year - 1


def _profile_row(db, student_id: str) -> StudentProfile | None:
    return db.get(StudentProfile, student_id)


def current_semester(db, student: Student) -> int:
    row = _profile_row(db, student.student_id)
    return row.semester if row else default_semester(student.year)


def get_profile(student_id: str) -> StudentProfileView | None:
    with db_session.SessionLocal() as db:
        student = db.get(Student, student_id)
        if student is None:
            return None
        row = _profile_row(db, student_id)
        codes = row.electives if row else []
        electives = (
            [
                ElectiveInfo(course_code=c.course_code, name=c.name, credits=c.credits)
                for c in db.scalars(select(Course).where(Course.course_code.in_(codes)).order_by(Course.course_code))
            ]
            if codes
            else []
        )
        return StudentProfileView(
            student_id=student.student_id,
            name=student.name,
            program=student.program,
            year=student.year,
            semester=row.semester if row else default_semester(student.year),
            section=row.section if row else None,
            electives=electives,
            preferences=Preferences(**(row.preferences if row else {})),
        )


def update_preferences(student_id: str, preferences: Preferences) -> StudentProfileView | None:
    with db_session.SessionLocal() as db:
        student = db.get(Student, student_id)
        if student is None:
            return None
        row = _profile_row(db, student_id)
        if row is None:
            row = StudentProfile(
                student_id=student_id, semester=default_semester(student.year), electives=[], preferences={}
            )
            db.add(row)
        # Assign a new dict: JSON columns are not change-tracked when mutated in place.
        row.preferences = preferences.model_dump()
        db.commit()
    return get_profile(student_id)


def attendance_report(student_id: str) -> dict:
    """Attendance in each course of the running semester, with how far each is
    from the 75% needed, and what it would take to get there."""
    with db_session.SessionLocal() as db:
        student = db.get(Student, student_id)
        if student is None:
            return {"error": "No student record was found."}
        semester = current_semester(db, student)
        rows = db.execute(
            select(AcademicRecord, Course)
            .join(Course, Course.course_code == AcademicRecord.course_code)
            .where(AcademicRecord.student_id == student_id, AcademicRecord.semester == semester)
            .order_by(Course.course_code)
        ).all()

    courses = []
    for record, course in rows:
        if record.total == 0:
            continue
        percentage = round(100 * record.attended / record.total, 1)
        if percentage >= ATTENDANCE_REQUIRED:
            status = "ok"
        elif percentage >= CONDONATION_FLOOR:
            status = "short"  # may apply for condonation of shortage
        else:
            status = "critical"  # not eligible for the end-semester exam
        # Classes to attend in a row, with none missed, to reach exactly 75%.
        needed = max(0, math.ceil((ATTENDANCE_REQUIRED / 100 * record.total - record.attended) / (1 - ATTENDANCE_REQUIRED / 100)))
        courses.append(
            {
                "course_code": course.course_code,
                "name": course.name,
                "attended": record.attended,
                "total": record.total,
                "percentage": percentage,
                "status": status,
                "classes_to_reach_75": needed,
            }
        )
    return {
        "semester": semester,
        "required_percentage": ATTENDANCE_REQUIRED,
        "condonation_floor": CONDONATION_FLOOR,
        "courses": courses,
        "below_required": [c["course_code"] for c in courses if c["status"] != "ok"],
    }


def cgpa(student_id: str) -> dict:
    """SGPA for each completed semester and the overall CGPA, as credit-weighted
    averages. A failed course counts with zero grade points and keeps its credits
    in the total, as the grading policy says."""
    with db_session.SessionLocal() as db:
        if db.get(Student, student_id) is None:
            return {"error": "No student record was found."}
        rows = db.execute(
            select(AcademicRecord, Course)
            .join(Course, Course.course_code == AcademicRecord.course_code)
            .where(AcademicRecord.student_id == student_id, AcademicRecord.grade.is_not(None))
            .order_by(AcademicRecord.semester, Course.course_code)
        ).all()

    if not rows:
        return {"cgpa": None, "semesters": [], "backlogs": [], "message": "No semester results are available yet."}

    by_semester: dict[int, list[tuple[int, int]]] = {}
    backlogs = []
    for record, course in rows:
        points = GRADE_POINTS[record.grade]
        by_semester.setdefault(record.semester, []).append((course.credits, points))
        if record.grade == "F":
            backlogs.append({"course_code": course.course_code, "name": course.name, "semester": record.semester})

    def average(pairs: list[tuple[int, int]]) -> float:
        return round(sum(c * p for c, p in pairs) / sum(c for c, _ in pairs), 2)

    everything = [pair for pairs in by_semester.values() for pair in pairs]
    return {
        "cgpa": average(everything),
        "credits_counted": sum(c for c, _ in everything),
        "semesters": [{"semester": s, "sgpa": average(pairs)} for s, pairs in sorted(by_semester.items())],
        "backlogs": backlogs,
    }
