import re
from datetime import date, datetime, timedelta

from sqlalchemy import func, select, update

from app.core import clock
from app.core.errors import AppError
from app.db import session as db_session
from app.db.models import CounsellingSlot, GrievanceTicket, Student, User
from app.services.schedule_service import WEEKDAYS

GRIEVANCE_CATEGORIES = ("academic-administrative", "fees", "hostel", "administrative", "interpersonal", "other")
ACKNOWLEDGE_WORKING_DAYS = 3
OUTCOME_DAYS = 28
MAX_SLOTS_SHOWN = 12

# Anything that could involve ragging, harassment or a threat to safety belongs with the
# bodies that deal with it, never in a general ticket. This is a deliberately broad net.
_SAFETY = re.compile(
    r"ragg|harass|assault|abus|molest|stalk|bully|bullied|threat|intimidat|unsafe|violen|blackmail|"
    r"suicid|self[- ]harm|hurt myself|kill myself|end my life",
    re.IGNORECASE,
)
_GRADES = re.compile(r"revaluat|re-evaluat|re-?check my (marks|paper)|grade review|marks? (were|was|are) (wrong|incorrect)", re.IGNORECASE)

SAFETY_GUIDANCE = (
    "This could involve ragging, harassment or your safety, which takes priority over everything else and is not "
    "handled as a general grievance. Please go to real help straight away: the Anti-Ragging Committee, the Internal "
    "Complaints Committee, your hostel warden, the Dean of Student Affairs office or campus security. If you are "
    "struggling emotionally, the Student Counselling Centre on the first floor of the Student Activity Centre takes "
    "walk-ins on weekday mornings."
)
GRADE_GUIDANCE = (
    "Complaints about a specific grade follow the grade-review and revaluation process run by the Registrar's "
    "Examinations Cell, not the general grievance committee."
)


def screen_grievance(category: str, description: str) -> str | None:
    """The reason a general ticket must not be raised, or None."""
    if _SAFETY.search(description) or _SAFETY.search(category):
        return SAFETY_GUIDANCE
    if _GRADES.search(description):
        return GRADE_GUIDANCE
    return None


def ticket_ref(ticket_id: int) -> str:
    return f"GR-{ticket_id:05d}"


def add_working_days(start: date, days: int) -> date:
    current = start
    while days:
        current += timedelta(days=1)
        if current.weekday() < 5:
            days -= 1
    return current


def create_ticket(student_id: str, category: str, description: str) -> str:
    with db_session.SessionLocal() as db:
        row = GrievanceTicket(student_id=student_id, category=category, description=description)
        db.add(row)
        db.commit()
        return ticket_ref(row.id)


def _describe(row: GrievanceTicket) -> dict:
    created = row.created_at.date()
    return {
        "ticket": ticket_ref(row.id),
        "category": row.category,
        "status": row.status,
        "submitted": created.isoformat(),
        "last_updated": row.updated_at.date().isoformat(),
        "acknowledgement_due_by": add_working_days(created, ACKNOWLEDGE_WORKING_DAYS).isoformat(),
        "outcome_expected_by": (created + timedelta(days=OUTCOME_DAYS)).isoformat(),
        "resolution_note": row.resolution_note,
    }


def grievance_status(student_id: str, ticket: str | None = None) -> dict:
    """One of the student's own tickets, or all of them. Someone else's ticket looks like one that does not exist."""
    with db_session.SessionLocal() as db:
        query = select(GrievanceTicket).where(GrievanceTicket.student_id == student_id)
        if ticket and ticket.strip():
            match = re.fullmatch(r"(?:GR-?)?0*(\d+)", ticket.strip(), re.IGNORECASE)
            if match is None:
                return {"error": "A ticket number looks like GR-00012."}
            row = db.scalar(query.where(GrievanceTicket.id == int(match.group(1))))
            return _describe(row) if row else {"error": f"No ticket {ticket.strip().upper()} was found for you."}
        rows = db.scalars(query.order_by(GrievanceTicket.id.desc()).limit(10)).all()
    if not rows:
        return {"tickets": [], "message": "You have not submitted any grievances."}
    return {"tickets": [_describe(r) for r in rows]}


def _slot_start(slot: CounsellingSlot) -> datetime:
    return datetime.strptime(f"{slot.date} {slot.start}", "%Y-%m-%d %H:%M")


def counselling_slots(student_id: str) -> dict:
    """Free appointment slots, and the student's own upcoming appointment if any."""
    now = clock.now()
    with db_session.SessionLocal() as db:
        rows = db.scalars(select(CounsellingSlot).where(CounsellingSlot.date >= now.date().isoformat()).order_by(CounsellingSlot.date, CounsellingSlot.start)).all()
    upcoming = [s for s in rows if _slot_start(s) > now]
    mine = next((s for s in upcoming if s.booked_by == student_id), None)
    free = [s for s in upcoming if s.booked_by is None][:MAX_SLOTS_SHOWN]
    return {
        "slots": [
            {"slot_id": s.id, "date": s.date, "weekday": WEEKDAYS[date.fromisoformat(s.date).weekday()], "start": s.start, "end": s.end}
            for s in free
        ],
        "your_appointment": None if mine is None else {"slot_id": mine.id, "date": mine.date, "start": mine.start, "end": mine.end},
        "about": "Sessions are confidential, one-to-one and free for enrolled students. The Counselling Centre is on the first floor of the Student Activity Centre and also takes walk-ins on weekday mornings.",
    }


def check_counselling_booking(student_id: str, slot_id) -> CounsellingSlot:
    if isinstance(slot_id, bool) or not isinstance(slot_id, int):
        raise ValueError("I need the slot number from the list of free slots.")
    now = clock.now()
    with db_session.SessionLocal() as db:
        slot = db.get(CounsellingSlot, slot_id)
        if slot is None or _slot_start(slot) <= now:
            raise ValueError("That slot isn't available. Look at the current list of free slots.")
        if slot.booked_by is not None:
            raise ValueError("That slot has just been taken. Please pick another.")
        later = db.scalars(select(CounsellingSlot).where(CounsellingSlot.booked_by == student_id)).all()
        if any(_slot_start(s) > now for s in later):
            raise ValueError("You already have an upcoming counselling appointment.")
        return slot


def book_counselling(student_id: str, slot_id: int) -> CounsellingSlot:
    check_counselling_booking(student_id, slot_id)
    with db_session.SessionLocal() as db:
        taken = db.execute(
            update(CounsellingSlot).where(CounsellingSlot.id == slot_id, CounsellingSlot.booked_by.is_(None)).values(booked_by=student_id)
        )
        db.commit()
        if taken.rowcount != 1:
            raise ValueError("That slot has just been taken. Please pick another.")
        return db.get(CounsellingSlot, slot_id)


GRIEVANCE_STATUSES = ("open", "in_progress", "resolved")
MAX_NOTE_CHARS = 2000


def parse_ticket_id(value: str) -> int | None:
    match = re.fullmatch(r"(?:GR-?)?0*(\d+)", str(value).strip(), re.IGNORECASE)
    return int(match.group(1)) if match else None


def _admin_view(row, student) -> dict:
    return {
        "id": row.id,
        "ticket": ticket_ref(row.id),
        "student_id": row.student_id,
        "student_name": student.name,
        "program": student.program,
        "category": row.category,
        "description": row.description,
        "status": row.status,
        "resolution_note": row.resolution_note,
        "submitted": row.created_at.isoformat(),
        "updated": row.updated_at.isoformat(),
    }


def list_grievances(status: str | None = None, limit: int = 500) -> dict:
    """Tickets for the committee, newest first, with the count in each status."""
    with db_session.SessionLocal() as db:
        counts = dict(db.execute(select(GrievanceTicket.status, func.count()).group_by(GrievanceTicket.status)).all())
        query = select(GrievanceTicket, Student).join(Student, Student.student_id == GrievanceTicket.student_id)
        if status:
            query = query.where(GrievanceTicket.status == status)
        rows = db.execute(query.order_by(GrievanceTicket.id.desc()).limit(limit)).all()
    return {
        "tickets": [_admin_view(t, s) for t, s in rows],
        "counts": {s: counts.get(s, 0) for s in GRIEVANCE_STATUSES},
    }


def update_grievance(ticket_id: int, status: str, note: str | None) -> dict:
    """Set a ticket's status and resolution note. Returns the ticket, whether the status
    changed, and the student's email address for the notification (None if they have no account)."""
    if status not in GRIEVANCE_STATUSES:
        raise AppError(422, "invalid_status", "The status must be one of: " + ", ".join(GRIEVANCE_STATUSES) + ".")
    note = (note or "").strip() or None
    if note and len(note) > MAX_NOTE_CHARS:
        raise AppError(422, "note_too_long", f"The note can be at most {MAX_NOTE_CHARS} characters.")
    if status == "resolved" and not note:
        raise AppError(422, "note_required", "Add a resolution note before marking a ticket resolved: the student is told the outcome.")
    with db_session.SessionLocal() as db:
        row = db.get(GrievanceTicket, ticket_id)
        if row is None:
            raise AppError(404, "not_found", "No such ticket.")
        changed = row.status != status
        row.status = status
        row.resolution_note = note
        db.commit()
        db.refresh(row)
        student = db.get(Student, row.student_id)
        email = db.scalar(select(User.email).where(User.student_id == row.student_id, User.is_active.is_(True)))
        return {"ticket": _admin_view(row, student), "status_changed": changed, "student_email": email}
