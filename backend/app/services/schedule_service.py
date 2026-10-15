from datetime import date, timedelta

from sqlalchemy import select

from app.core import clock
from app.db import session as db_session
from app.db.models import Course, Exam, Student, StudentProfile, TimetableSlot
from app.services.academic_service import current_semester

WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
_ABBREVIATIONS = {name[:3].lower(): index for index, name in enumerate(WEEKDAYS)}


class _BadDay(ValueError):
    pass


def _parse_day(day: str | None, today: date) -> tuple[list[int], date | None]:
    """The weekday numbers a request covers, and the date when it names one
    ("today", "tomorrow"). "week" covers the five teaching days."""
    word = (day or "").strip().lower() or "today"
    if word == "today":
        return [today.weekday()], today
    if word == "tomorrow":
        return [(today + timedelta(days=1)).weekday()], today + timedelta(days=1)
    if word in ("week", "this week", "all"):
        return list(range(5)), None
    index = _ABBREVIATIONS.get(word[:3])
    if index is None or not WEEKDAYS[index].lower().startswith(word):
        raise _BadDay(f"'{day}' is not a day. Use a weekday name, 'today', 'tomorrow' or 'week'.")
    return [index], None


def _group(db, student_id: str) -> tuple[Student, StudentProfile | None, int]:
    student = db.get(Student, student_id)
    profile = db.get(StudentProfile, student_id) if student else None
    return student, profile, (current_semester(db, student) if student else 0)


def timetable(student_id: str, day: str | None = None) -> dict:
    """The student's classes for a day, or for the whole week."""
    try:
        weekdays, on_date = _parse_day(day, clock.today())
    except _BadDay as exc:
        return {"error": str(exc)}

    with db_session.SessionLocal() as db:
        student, profile, semester = _group(db, student_id)
        if student is None:
            return {"error": "No student record was found."}
        if profile is None or not profile.section:
            return {"error": "Your class section is not recorded, so your timetable cannot be shown."}
        rows = db.execute(
            select(TimetableSlot, Course)
            .join(Course, Course.course_code == TimetableSlot.course_code)
            .where(
                TimetableSlot.department == student.program,
                TimetableSlot.semester == semester,
                TimetableSlot.section == profile.section,
                TimetableSlot.day.in_(weekdays),
            )
            .order_by(TimetableSlot.day, TimetableSlot.start)
        ).all()
        section = profile.section

    by_day: dict[int, list[dict]] = {d: [] for d in weekdays}
    for slot, course in rows:
        by_day[slot.day].append(
            {
                "start": slot.start,
                "end": slot.end,
                "course_code": course.course_code,
                "name": course.name,
                "kind": course.kind,
                "room": slot.room,
            }
        )
    result = {"semester": semester, "section": section}
    if len(weekdays) == 1:
        result.update(day=WEEKDAYS[weekdays[0]], date=on_date.isoformat() if on_date else None, classes=by_day[weekdays[0]])
        if weekdays[0] >= 5:
            result["message"] = "There are no classes at the weekend."
        elif not by_day[weekdays[0]]:
            result["message"] = "No classes are scheduled for this day."
    else:
        result["week"] = [{"day": WEEKDAYS[d], "classes": by_day[d]} for d in weekdays]
    return result


def exam_schedule(student_id: str, semester: int | None = None) -> dict:
    """The exams for the student's courses in a semester (the current one by default)."""
    today = clock.today()
    with db_session.SessionLocal() as db:
        student, _, current = _group(db, student_id)
        if student is None:
            return {"error": "No student record was found."}
        wanted = current if semester is None else semester
        if not 1 <= wanted <= 8:
            return {"error": "The semester must be between 1 and 8."}
        rows = db.execute(
            select(Exam, Course)
            .join(Course, Course.course_code == Exam.course_code)
            .where(Course.department == student.program, Course.semester == wanted)
            .order_by(Exam.date, Exam.start_time)
        ).all()

    if not rows:
        return {"semester": wanted, "exams": [], "message": f"No exam schedule has been published for semester {wanted}."}
    exams = []
    for exam, course in rows:
        when = date.fromisoformat(exam.date)
        exams.append(
            {
                "course_code": course.course_code,
                "course": course.name,
                "exam": exam.name,
                "type": exam.exam_type,
                "date": exam.date,
                "weekday": WEEKDAYS[when.weekday()],
                "start_time": exam.start_time,
                "duration_minutes": exam.duration_minutes,
                "venue": exam.venue,
                "status": "upcoming" if when > today else "today" if when == today else "past",
                "days_until": (when - today).days if when >= today else None,
            }
        )
    return {"semester": wanted, "exams": exams}
