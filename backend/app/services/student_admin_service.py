import csv
import io
import re

from sqlalchemy import func, or_, select

from app.core.errors import AppError
from app.db import session as db_session
from app.db.models import AcademicRecord, Course, GrievanceTicket, Registration, Event, Student, StudentProfile, User
from app.models.ids import STUDENT_ID_PATTERN
from app.services import academic_service, support_service

MAX_PAGE_SIZE = 100
MAX_IMPORT_BYTES = 1024 * 1024
MAX_IMPORT_ROWS = 5000
MAX_REPORTED_ERRORS = 50
IMPORT_COLUMNS = ("student_id", "name", "program", "year")


def list_students(page: int, page_size: int, q: str | None, program: str | None, year: int | None) -> dict:
    """A page of the roster, with a search over id and name and filters on program and year."""
    page_size = min(max(page_size, 1), MAX_PAGE_SIZE)
    query = select(Student)
    if q and q.strip():
        word = q.strip().lower()
        query = query.where(
            or_(
                func.lower(Student.student_id).contains(word, autoescape=True),
                func.lower(Student.name).contains(word, autoescape=True),
            )
        )
    if program:
        query = query.where(Student.program == program)
    if year:
        query = query.where(Student.year == year)
    with db_session.SessionLocal() as db:
        total = db.scalar(select(func.count()).select_from(query.subquery()))
        rows = db.scalars(query.order_by(Student.student_id).limit(page_size).offset((max(page, 1) - 1) * page_size)).all()
        with_accounts = set(db.scalars(select(User.student_id).where(User.student_id.in_([s.student_id for s in rows]))))
        programs = list(db.scalars(select(Student.program).distinct().order_by(Student.program)))
    return {
        "items": [
            {"student_id": s.student_id, "name": s.name, "program": s.program, "year": s.year, "has_account": s.student_id in with_accounts}
            for s in rows
        ],
        "page": max(page, 1),
        "page_size": page_size,
        "total": total,
        "programs": programs,
    }


def student_detail(student_id: str) -> dict:
    """Everything the university holds about one student, for an administrator."""
    with db_session.SessionLocal() as db:
        student = db.get(Student, student_id)
        if student is None:
            raise AppError(404, "not_found", f"No student '{student_id}'.")
        profile = db.get(StudentProfile, student_id)
        account = db.scalar(select(User).where(User.student_id == student_id))
        records = db.execute(
            select(AcademicRecord, Course)
            .join(Course, Course.course_code == AcademicRecord.course_code)
            .where(AcademicRecord.student_id == student_id)
            .order_by(AcademicRecord.semester, Course.course_code)
        ).all()
        registrations = db.execute(
            select(Registration, Event).join(Event, Event.id == Registration.event_id).where(Registration.student_id == student_id).order_by(Event.date)
        ).all()
        tickets = db.scalars(select(GrievanceTicket).where(GrievanceTicket.student_id == student_id).order_by(GrievanceTicket.id.desc())).all()
    summary = academic_service.cgpa(student_id)
    return {
        "student_id": student.student_id,
        "name": student.name,
        "program": student.program,
        "year": student.year,
        "semester": profile.semester if profile else academic_service.default_semester(student.year),
        "section": profile.section if profile else None,
        "interests": (profile.preferences or {}).get("interests", []) if profile else [],
        "account": {"email": account.email, "active": account.is_active} if account else None,
        "cgpa": summary.get("cgpa"),
        "backlogs": summary.get("backlogs", []),
        "records": [
            {
                "semester": r.semester,
                "course_code": c.course_code,
                "course": c.name,
                "credits": c.credits,
                "attended": r.attended,
                "total": r.total,
                "grade": r.grade,
            }
            for r, c in records
        ],
        "registrations": [
            {"registration_id": r.registration_id, "event_id": e.id, "event": e.name, "date": e.date, "status": r.status} for r, e in registrations
        ],
        "tickets": [
            {"ticket": support_service.ticket_ref(t.id), "category": t.category, "status": t.status, "submitted": t.created_at.date().isoformat()}
            for t in tickets
        ],
    }


def import_students(data: bytes) -> dict:
    """Add students from a CSV with the columns student_id, name, program, year.

    All or nothing: if any row is invalid nothing is added and every problem is
    reported. Students already on the roster are left as they are."""
    if len(data) > MAX_IMPORT_BYTES:
        raise AppError(413, "file_too_large", f"The file can be at most {MAX_IMPORT_BYTES // 1024} KB.")
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise AppError(422, "invalid_csv", "The file is not UTF-8 text.") from None
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None or not set(IMPORT_COLUMNS) <= {(f or "").strip() for f in reader.fieldnames}:
        raise AppError(422, "invalid_csv", "The first row must contain the columns: " + ", ".join(IMPORT_COLUMNS) + ".")

    errors: list[dict] = []
    seen: dict[str, int] = {}
    rows: list[dict] = []
    for line, raw in enumerate(reader, start=2):
        if line - 1 > MAX_IMPORT_ROWS:
            raise AppError(422, "too_many_rows", f"At most {MAX_IMPORT_ROWS} students can be imported at once.")
        row = {(k or "").strip(): (v or "").strip() for k, v in raw.items() if k}
        problems = []
        if not re.fullmatch(STUDENT_ID_PATTERN, row.get("student_id", "")):
            problems.append("student_id must look like 1RV23IS101")
        if not 1 <= len(row.get("name", "")) <= 100:
            problems.append("name must be 1 to 100 characters")
        if not 1 <= len(row.get("program", "")) <= 100:
            problems.append("program must be 1 to 100 characters")
        if row.get("year", "") not in ("1", "2", "3", "4"):
            problems.append("year must be 1, 2, 3 or 4")
        if not problems and row["student_id"] in seen:
            problems.append(f"student_id repeats line {seen[row['student_id']]}")
        for problem in problems:
            errors.append({"line": line, "message": problem})
        if not problems:
            seen[row["student_id"]] = line
            rows.append({**row, "year": int(row["year"])})
    if errors:
        raise AppError(422, "invalid_rows", f"{len(errors)} problems found, nothing was imported. First: line {errors[0]['line']}: {errors[0]['message']}.")
    if not rows:
        raise AppError(422, "invalid_csv", "The file has no student rows.")

    with db_session.SessionLocal() as db:
        existing = set(db.scalars(select(Student.student_id).where(Student.student_id.in_([r["student_id"] for r in rows]))))
        fresh = [r for r in rows if r["student_id"] not in existing]
        db.add_all(Student(student_id=r["student_id"], name=r["name"], program=r["program"], year=r["year"]) for r in fresh)
        db.commit()
    return {"created": len(fresh), "skipped_existing": sorted(existing)}
