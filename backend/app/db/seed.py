import json
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import DATA_DIR
from app.db import session as db_session
from app.db.models import (
    AcademicRecord,
    Book,
    BookLoan,
    BusRoute,
    CanteenItem,
    CounsellingSlot,
    Course,
    CourseOffering,
    Event,
    Exam,
    FacultyMember,
    FeeRecord,
    LostFoundItem,
    PlacementDrive,
    Registration,
    Student,
    StudentProfile,
    StudyRoom,
    TimetableSlot,
)


def _load(filename: str) -> list[dict]:
    return json.loads((DATA_DIR / filename).read_text())


def _is_empty(session: Session, model) -> bool:
    return session.scalar(select(func.count()).select_from(model)) == 0


def seed(session: Session) -> dict[str, int]:
    """Load data/*.json into any table that is still empty.

    Safe to run repeatedly: a table that already has rows is left untouched,
    so re-seeding never duplicates data or overwrites live registrations.
    """
    added: dict[str, int] = {}

    added.update(students=0, events=0, registrations=0)
    if _is_empty(session, Student):
        rows = [Student(**row) for row in _load("students.json")]
        session.add_all(rows)
        added["students"] = len(rows)

    if _is_empty(session, Event):
        rows = [Event(**row) for row in _load("events.json")]
        session.add_all(rows)
        added["events"] = len(rows)

    if _is_empty(session, Registration):
        rows = [
            Registration(
                registration_id=row["registration_id"],
                student_id=row["student_id"],
                event_id=row["event_id"],
                registered_at=datetime.fromisoformat(row["registered_at"]),
                status=row["status"],
            )
            for row in _load("registrations.json")
        ]
        session.add_all(rows)
        added["registrations"] = len(rows)

    # Courses before the records that refer to them, faculty before the courses they
    # teach; students were added above.
    for table, model, filename in (
        ("courses", Course, "courses.json"),
        ("student_profiles", StudentProfile, "student_profiles.json"),
        ("academic_records", AcademicRecord, "academic_records.json"),
        ("faculty_members", FacultyMember, "faculty_members.json"),
        ("course_offerings", CourseOffering, "course_offerings.json"),
        ("timetable_slots", TimetableSlot, "timetable_slots.json"),
        ("exams", Exam, "exams.json"),
        ("fee_records", FeeRecord, "fee_records.json"),
        ("books", Book, "books.json"),
        ("book_loans", BookLoan, "book_loans.json"),
        ("canteen_menu", CanteenItem, "canteen_menu.json"),
        ("study_rooms", StudyRoom, "study_rooms.json"),
        ("bus_routes", BusRoute, "bus_routes.json"),
        ("lost_found_items", LostFoundItem, "lost_found_items.json"),
        ("counselling_slots", CounsellingSlot, "counselling_slots.json"),
        ("placement_drives", PlacementDrive, "placement_drives.json"),
    ):
        added[table] = 0
        if _is_empty(session, model):
            rows = [model(**row) for row in _load(filename)]
            session.add_all(rows)
            session.flush()
            added[table] = len(rows)

    session.commit()
    return added


def main() -> None:
    with db_session.SessionLocal() as session:
        added = seed(session)
    for table, count in added.items():
        print(f"{table}: {'added ' + str(count) if count else 'already populated, skipped'}")


if __name__ == "__main__":
    main()
