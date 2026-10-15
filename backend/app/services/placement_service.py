from datetime import date

from sqlalchemy import func, select

from app.core import clock
from app.db import session as db_session
from app.db.models import AcademicRecord, PlacementDrive, Student
from app.services import academic_service

CONFIRM_NOTE = (
    "Each recruiter sets its own criteria. Confirm eligibility for a specific company with the Placement Cell "
    "before relying on this."
)


def _describe(drive: PlacementDrive, today: date) -> dict:
    return {
        "drive_id": drive.drive_id,
        "company": drive.company,
        "role": drive.role,
        "kind": drive.kind,
        "date": drive.date,
        "venue": drive.venue,
        "registration_deadline": drive.registration_deadline,
        "registration_open": drive.registration_deadline >= today.isoformat(),
        "min_cgpa": drive.min_cgpa,
        "max_active_backlogs": drive.max_active_backlogs,
        "departments": drive.departments,
        "who_can_attend": "final-year students" if drive.kind == "full-time" else "pre-final-year students",
    }


def _iso(value: str | None, label: str) -> str | None:
    if not value or not value.strip():
        return None
    try:
        return date.fromisoformat(value.strip()).isoformat()
    except ValueError:
        raise ValueError(f"{label} must be a date like 2026-11-20.") from None


def drives(company: str | None = None, from_date: str | None = None, to_date: str | None = None) -> dict:
    """Upcoming placement drives, optionally for one company or a range of dates."""
    today = clock.today()
    try:
        start = _iso(from_date, "from_date") or today.isoformat()
        end = _iso(to_date, "to_date")
    except ValueError as exc:
        return {"error": str(exc)}
    with db_session.SessionLocal() as db:
        query = select(PlacementDrive).where(PlacementDrive.date >= start).order_by(PlacementDrive.date, PlacementDrive.drive_id)
        if end:
            query = query.where(PlacementDrive.date <= end)
        if company and company.strip():
            query = query.where(func.lower(PlacementDrive.company).contains(company.strip().lower(), autoescape=True))
        rows = db.scalars(query).all()
    result = {"drives": [_describe(d, today) for d in rows], "note": CONFIRM_NOTE}
    if not rows:
        result["message"] = "No upcoming drives match."
    return result


def eligibility(student_id: str, drive: str) -> dict:
    """Whether the student meets a drive's criteria, criterion by criterion."""
    today = clock.today()
    key = drive.strip()
    with db_session.SessionLocal() as db:
        student = db.get(Student, student_id)
        if student is None:
            return {"error": "No student record was found."}
        found = db.get(PlacementDrive, key.upper())
        if found is None:
            matches = db.scalars(
                select(PlacementDrive).where(func.lower(PlacementDrive.company).contains(key.lower(), autoescape=True)).order_by(PlacementDrive.date)
            ).all() if key else []
            if not matches:
                return {"error": f"No placement drive matches '{key}'. List the upcoming drives first."}
            if len(matches) > 1:
                return {
                    "matches": [{"drive_id": m.drive_id, "company": m.company, "role": m.role, "kind": m.kind} for m in matches],
                    "message": "Several drives match. Ask which one is meant.",
                }
            found = matches[0]
        backlogs = db.scalar(
            select(func.count()).select_from(AcademicRecord).where(AcademicRecord.student_id == student_id, AcademicRecord.grade == "F")
        )
    cgpa = academic_service.cgpa(student_id).get("cgpa")
    year_needed = 4 if found.kind == "full-time" else 3
    departments = found.departments
    checks = [
        {"criterion": "year of study", "required": f"year {year_needed} ({'final' if year_needed == 4 else 'pre-final'} year)", "actual": f"year {student.year}", "met": student.year == year_needed},
        {"criterion": "department", "required": "any" if departments == "all" else ", ".join(departments), "actual": student.program, "met": departments == "all" or student.program in departments},
        {"criterion": "CGPA", "required": f"at least {found.min_cgpa}", "actual": cgpa if cgpa is not None else "no results yet", "met": cgpa is not None and cgpa >= found.min_cgpa},
        {"criterion": "active backlogs", "required": f"at most {found.max_active_backlogs}", "actual": backlogs, "met": backlogs <= found.max_active_backlogs},
    ]
    return {
        "drive": _describe(found, today),
        "eligible": all(c["met"] for c in checks),
        "checks": checks,
        "reminder": "Students must also register their profile with the Placement Cell by the registration deadline.",
        "note": CONFIRM_NOTE,
    }
