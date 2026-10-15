import re

from sqlalchemy import func, select

from app.db import session as db_session
from app.db.models import Course, CourseOffering, FacultyMember

MAX_MATCHES = 5
_TITLE = re.compile(r"^(?:dr|prof|mr|ms)\.?(?:\s+|$)", re.IGNORECASE)


def course_info(course_code: str) -> dict:
    """What a course is, who teaches it and how many hours a week it takes."""
    code = course_code.strip().upper()
    with db_session.SessionLocal() as db:
        row = db.execute(
            select(Course, CourseOffering, FacultyMember)
            .outerjoin(CourseOffering, CourseOffering.course_code == Course.course_code)
            .outerjoin(FacultyMember, FacultyMember.faculty_id == CourseOffering.faculty_id)
            .where(Course.course_code == code)
        ).first()
    if row is None:
        return {"error": f"No course with the code {code} was found."}
    course, offering, teacher = row
    info = {
        "course_code": course.course_code,
        "name": course.name,
        "credits": course.credits,
        "department": course.department,
        "semester": course.semester,
        "kind": course.kind,
        "instructor": (
            {"faculty_id": teacher.faculty_id, "name": teacher.name, "designation": teacher.designation}
            if teacher
            else None
        ),
        "weekly_hours": (
            {"lecture": offering.lecture_hours, "practical": offering.practical_hours} if offering else None
        ),
        "note": (
            "The detailed syllabus and how marks are weighted are in the course handout that the "
            "instructor gives out in the first week of the semester."
        ),
    }
    return info


def faculty_profile(query: str) -> dict:
    """A faculty member's directory entry, found by faculty id or by name."""
    text = query.strip()
    if not text:
        return {"error": "Give a faculty id or a name to look up."}
    with db_session.SessionLocal() as db:
        by_id = db.get(FacultyMember, text.upper())
        if by_id is not None:
            matches = [by_id]
        else:
            words = _TITLE.sub("", text).lower().split()
            if not words:
                return {"error": "Give a faculty id or a name to look up."}
            matches = list(
                db.scalars(
                    select(FacultyMember)
                    .where(*(func.lower(FacultyMember.name).contains(w, autoescape=True) for w in words))
                    .order_by(FacultyMember.faculty_id)
                )
            )
        if not matches:
            return {"error": f"No faculty member matching '{text}' was found."}
        if len(matches) > 1:
            return {
                "matches": [
                    {"faculty_id": m.faculty_id, "name": m.name, "designation": m.designation, "department": m.department}
                    for m in matches[:MAX_MATCHES]
                ],
                "message": f"{len(matches)} faculty members match. Ask which one is meant.",
            }
        person = matches[0]
        teaching = db.execute(
            select(Course.course_code, Course.name)
            .join(CourseOffering, CourseOffering.course_code == Course.course_code)
            .where(CourseOffering.faculty_id == person.faculty_id)
            .order_by(Course.course_code)
        ).all()
    return {
        "faculty_id": person.faculty_id,
        "name": person.name,
        "designation": person.designation,
        "department": person.department,
        "specialisation": person.specialisation,
        "leadership_role": person.leadership_role,
        "office": person.office,
        "office_hours": person.office_hours,
        "email": person.email,
        "teaches": [{"course_code": code, "name": name} for code, name in teaching],
    }
