from sqlalchemy import select

from app.db.models import Event, Registration
from app.models.auth import CurrentStudent


def all_registrations(factory):
    with factory() as session:
        return list(session.scalars(select(Registration).order_by(Registration.id)))


def event_registered(factory, event_id):
    with factory() as session:
        return session.get(Event, event_id).registered


ASHA = {"student_id": "1RV23IS101", "name": "Asha", "email": "asha@example.com", "password": "correct horse battery"}
RAVI = {"student_id": "1RV24IS219", "name": "Ravi", "email": "ravi@example.com", "password": "another long password"}


def sign_up(client, account=ASHA):
    """Register an account through the API; the client keeps the cookies."""
    response = client.post("/api/auth/register", json=account)
    assert response.status_code == 201, response.text
    return client


ASHA_PROFILE = CurrentStudent(
    user_id=1, student_id="1RV23IS101", name="Asha", program="ISE", year=3, email="asha@example.com"
)


ISE = "Information Science and Engineering"
CSE = "Computer Science and Engineering"
ADMIN = {"role": "admin", "name": "Root Admin", "email": "admin@example.com", "password": "admin password long"}
STAFF = {"role": "staff", "name": "Front Desk", "email": "staff@example.com", "password": "staff password long"}
FACULTY = {
    "role": "faculty", "name": "Dr. Rao", "email": "rao@example.com", "password": "faculty password long",
    "department": ISE, "office": "B-204", "office_hours": "Tue 2-4",
}
FACULTY_CSE = {**FACULTY, "name": "Dr. Iyer", "email": "iyer@example.com", "department": CSE}


def sign_in_as(account, **client_options):
    """Create a faculty/staff/admin account and return a client signed in as it."""
    from fastapi.testclient import TestClient

    from app.main import app
    from app.models.auth import NewStaffAccount
    from app.services import auth_service

    auth_service.create_staff_account(NewStaffAccount(**account))
    client = TestClient(app, **client_options)
    response = client.post("/api/auth/login", json={"email": account["email"], "password": account["password"]})
    assert response.status_code == 200, response.text
    return client


def insert_legacy_chunks(store, rows):
    """Put chunks into a store the way the first version of ingestion did, with only
    a document and section recorded (no file hash, settings signature or time).
    rows: (id, text, document, section)."""
    from qdrant_client import models

    from app.rag import store as store_module

    if isinstance(store, store_module.ChromaStore):
        store._collection.add(
            ids=[r[0] for r in rows],
            documents=[r[1] for r in rows],
            metadatas=[{"document": r[2], "section": r[3]} for r in rows],
        )
        return

    vectors = store._embed([r[1] for r in rows])
    store._client.upsert(
        store_module.KNOWLEDGE_COLLECTION,
        points=[
            models.PointStruct(
                id=store._point_id(chunk_id),
                vector=vector,
                payload={"id": chunk_id, "text": text, "document": document, "section": section},
            )
            for (chunk_id, text, document, section), vector in zip(rows, vectors)
        ],
    )


def add_academic_data(factory):
    """Courses and records for Asha (year 3, so semester 5) and Ravi, small enough to
    work out by hand.

    Asha, completed:  A101 (4 credits) A=8, A102 (3) B+=7, A201 (4, semester 2) O=10.
    Asha, semester 5: 18 of 25 in A501, 27 of 28 in A502, 5 of 10 in A503.
    """
    from app.db.models import AcademicRecord, Course

    courses = [
        ("A101", "Mathematics I", 4, 1, "theory"),
        ("A102", "Physics", 3, 1, "theory"),
        ("A103", "Chemistry", 3, 1, "theory"),
        ("A201", "Data Structures", 4, 2, "theory"),
        ("A501", "Machine Learning", 4, 5, "theory"),
        ("A502", "Web Technologies", 3, 5, "theory"),
        ("A503", "ML Lab", 1, 5, "lab"),
        ("B301", "Ravi's Course", 3, 3, "theory"),
    ]
    records = [
        ("1RV23IS101", "A101", 1, 40, 40, "A"),
        ("1RV23IS101", "A102", 1, 38, 40, "B+"),
        ("1RV23IS101", "A201", 2, 40, 40, "O"),
        ("1RV23IS101", "A501", 5, 18, 25, None),
        ("1RV23IS101", "A502", 5, 27, 28, None),
        ("1RV23IS101", "A503", 5, 5, 10, None),
        ("1RV24IS219", "B301", 3, 10, 20, None),
    ]
    with factory.begin() as session:
        session.add_all(
            Course(course_code=c, name=n, credits=cr, department="ISE", semester=s, kind=k)
            for c, n, cr, s, k in courses
        )
        session.flush()
        session.add_all(
            AcademicRecord(student_id=sid, course_code=c, semester=s, attended=a, total=t, grade=g)
            for sid, c, s, a, t, g in records
        )


RAVI_PROFILE = CurrentStudent(
    user_id=2, student_id="1RV24IS219", name="Ravi", program="CSE", year=2, email="ravi@example.com"
)


def register_through_approval(student, event_id="evt_ai_001"):
    """Register a student the way the application does: the assistant proposes,
    the student approves."""
    from uuid import UUID

    from app.services import action_service

    confirmation = action_service.propose(student, "register_for_event", {"event_id": event_id})
    return action_service.confirm(UUID(confirmation.action_id), student)


def add_schedule_data(factory):
    """What the schedule, exam, fee and directory tools read, for Asha (ISE, semester 5,
    section A) and Ravi (CSE, semester 3, section A). Builds on add_academic_data.

    Asha's week: Monday 09:00 Machine Learning and 10:00 Web Technologies (section A), Tuesday
    14:00-16:00 the ML lab. Section B of the same semester has its own Monday class.
    """
    from app.db.models import (
        Course,
        CourseOffering,
        Exam,
        FacultyMember,
        FeeRecord,
        StudentProfile,
        TimetableSlot,
    )

    add_academic_data(factory)

    def person(fid, name, designation, department="ISE", **extra):
        return FacultyMember(
            faculty_id=fid, name=name, designation=designation, department=department,
            email=f"{fid.lower()}@campus.example", **extra,
        )

    def slot(dept, semester, section, day, start, end, code, room):
        return TimetableSlot(
            department=dept, semester=semester, section=section, day=day, start=start, end=end,
            course_code=code, room=room,
        )

    def exam(code, name, kind, day, start="09:30", minutes=180, venue="Examination Hall 1"):
        return Exam(
            course_code=code, name=name, exam_type=kind, date=day, start_time=start,
            duration_minutes=minutes, venue=venue,
        )

    def fee(student, term, component, amount, due, paid, paid_on=None):
        return FeeRecord(
            student_id=student, term=term, component=component, amount=amount, due_date=due,
            paid_amount=paid, paid_on=paid_on,
        )

    with factory.begin() as session:
        session.add_all(
            [
                Course(course_code="A504", name="Cloud Computing", credits=3, department="ISE", semester=5, kind="elective"),
                Course(course_code="A505", name="Data Mining", credits=3, department="ISE", semester=5, kind="elective"),
                Course(course_code="A701", name="Deep Learning", credits=3, department="ISE", semester=7, kind="elective"),
                Course(course_code="C301", name="Operating Systems", credits=4, department="CSE", semester=3, kind="theory"),
                StudentProfile(student_id="1RV23IS101", semester=5, section="A", electives=["A504"], preferences={}),
                StudentProfile(student_id="1RV24IS219", semester=3, section="A", electives=[], preferences={}),
                person("FAC-ISE-01", "Dr. Radhika Venkatesh", "Professor", leadership_role="Head of Department", office="Main Academic Block, Room 214"),
                person("FAC-ISE-04", "Dr. Farhan Sheikh", "Associate Professor", specialisation="artificial intelligence and machine learning", leadership_role="Vice-Chair for Research", office="Main Academic Block, Room 217", office_hours="Wed 15:00-16:00"),
                person("FAC-ISE-02", "Dr. Mohan Iyer", "Professor"),
                person("FAC-ISE-07", "Ms. Pooja Iyer", "Assistant Professor"),
                person("FAC-ISE-08", "Dr. Shalini D'Souza", "Associate Professor"),
            ]
        )
        session.flush()
        session.add_all(
            [
                CourseOffering(course_code="A501", faculty_id="FAC-ISE-04", lecture_hours=3, practical_hours=0),
                CourseOffering(course_code="A503", faculty_id="FAC-ISE-04", lecture_hours=0, practical_hours=2),
                slot("ISE", 5, "A", 0, "10:00", "11:00", "A502", "Classroom 5A"),
                slot("ISE", 5, "A", 0, "09:00", "10:00", "A501", "Classroom 5A"),
                slot("ISE", 5, "A", 1, "14:00", "16:00", "A503", "Lab 2"),
                slot("ISE", 5, "B", 0, "09:00", "10:00", "A502", "Classroom 5B"),
                slot("ISE", 3, "A", 0, "09:00", "10:00", "B301", "Classroom 3A"),
                slot("CSE", 3, "A", 0, "11:15", "12:15", "C301", "Classroom CS-3A"),
                exam("A501", "Internal Test 1", "internal", "2026-09-08", "14:00", 90, "Regular classroom"),
                exam("A501", "End-Semester Examination", "end-semester", "2026-11-23"),
                exam("A502", "End-Semester Examination", "end-semester", "2026-10-15", venue="Examination Hall 2"),
                exam("A503", "Practical Examination", "practical", "2026-11-17", venue="ISE Lab 1"),
                exam("B301", "End-Semester Examination", "end-semester", "2026-11-24"),
                exam("C301", "End-Semester Examination", "end-semester", "2026-11-25"),
                fee("1RV23IS101", "2026-27 odd", "Tuition Fee", 62500, "2026-07-15", 62500, "2026-07-10"),
                fee("1RV23IS101", "2026-27 odd", "Laboratory Fee", 6000, "2026-07-15", 0),
                fee("1RV23IS101", "2026-27 even", "Tuition Fee", 62500, "2026-12-15", 0),
                fee("1RV23IS101", "2026-27 even", "Laboratory Fee", 6000, "2026-12-15", 0),
                fee("1RV24IS219", "2026-27 odd", "Tuition Fee", 62500, "2026-07-15", 62500, "2026-07-01"),
            ]
        )


def add_operations_data(factory):
    """A small library, rooms, menu, routes, lost items, counselling slots and drives.

    Library: BK-1 has 2 copies, both out (Ravi, due 2026-10-20, and Arjun, due 2026-10-27) and Arjun holds it; BK-2
    has 3 copies with 1 out (Asha); BK-3 is a reference book; BK-4 has 2 copies on the shelf.
    """
    import json

    from app.db.models import (
        Book,
        BookLoan,
        BookReservation,
        BusRoute,
        CanteenItem,
        CounsellingSlot,
        LostFoundItem,
        PlacementDrive,
        StudyRoom,
    )

    def book(bid, title, author, copies, reference=False):
        return Book(
            book_id=bid, title=title, author=author, isbn=f"DEMO-{bid}", category="Computer Science",
            shelf_location="Reference Area" if reference else "First floor, shelf CO-01",
            copies_total=copies, reference_only=reference,
        )

    from app.db.models import Student

    with factory.begin() as session:
        session.add(Student(student_id="1RV22CS220", name="Arjun", program="CSE", year=4))
        session.flush()
        session.add_all(
            [
                book("BK-1", "Introduction to Algorithms", "Thomas Cormen", 2),
                book("BK-2", "Operating System Concepts", "Abraham Silberschatz", 3),
                book("BK-3", "Encyclopedia of Computer Science", "Various", 1, reference=True),
                book("BK-4", "Algorithms", "Robert Sedgewick", 2),
            ]
        )
        session.flush()
        session.add_all(
            [
                BookLoan(book_id="BK-1", student_id="1RV24IS219", borrowed_on="2026-10-06", due_date="2026-10-20"),
                BookLoan(book_id="BK-1", student_id="1RV22CS220", borrowed_on="2026-10-13", due_date="2026-10-27"),
                BookLoan(book_id="BK-2", student_id="1RV23IS101", borrowed_on="2026-10-01", due_date="2026-10-15"),
                StudyRoom(room_id="DR-1", name="Discussion Room 1", capacity=4, floor=2),
                StudyRoom(room_id="DR-7", name="Discussion Room 7", capacity=8, floor=2),
                CanteenItem(weekday=0, meal="breakfast", item="Idli", price=35, vegetarian=True),
                CanteenItem(weekday=0, meal="lunch", item="Full thali", price=90, vegetarian=True),
                CanteenItem(weekday=0, meal="lunch", item="Chicken biryani", price=110, vegetarian=False),
                CanteenItem(weekday=0, meal="dinner", item="Dal khichdi", price=55, vegetarian=True),
                CanteenItem(weekday=5, meal="breakfast", item="Poha", price=30, vegetarian=True),
                LostFoundItem(description="Black umbrella", location_found="Main Academic Block lobby", found_on="2026-10-10"),
                LostFoundItem(description="Blue water bottle", location_found="Central Cafeteria", found_on="2026-10-11"),
                LostFoundItem(description="Old umbrella", location_found="Library", found_on="2026-09-01", status="claimed"),
            ]
        )
        session.add(BookReservation(book_id="BK-1", student_id="1RV22CS220"))
        session.add_all(
            [
                BusRoute(
                    route_code="A", name="City Gate Line", stops=["Main Gate", "Central Library"],
                    service=[
                        {"days": [0, 1, 2, 3, 4], "start": "07:00", "end": "09:30", "every_minutes": 20},
                        {"days": [0, 1, 2, 3, 4], "start": "09:30", "end": "16:30", "every_minutes": 40},
                        {"days": [5], "start": "07:00", "end": "15:00", "every_minutes": 40},
                    ],
                    notes="Reduced on Saturday.",
                ),
                BusRoute(
                    route_code="B", name="Hostel Loop", stops=["Ashoka Block", "Nilgiri Block"],
                    service=[{"days": [0, 1, 2, 3, 4, 5, 6], "start": "07:00", "end": "22:00", "every_minutes": 15}],
                    notes="Every day.",
                ),
                BusRoute(
                    route_code="TOWN", name="Saturday Town Shuttle", stops=["Main Gate", "Town"],
                    service=[{"days": [5], "departures": ["10:00", "16:00"], "returns": ["13:00", "19:00"]}],
                    notes="Saturdays only.",
                ),
                CounsellingSlot(id=1, date="2026-10-14", start="14:00", end="14:45"),
                CounsellingSlot(id=2, date="2026-10-19", start="14:00", end="14:45"),
                CounsellingSlot(id=3, date="2026-10-19", start="15:00", end="15:45", booked_by="1RV24IS219"),
                CounsellingSlot(id=4, date="2026-10-20", start="14:00", end="14:45"),
                PlacementDrive(
                    drive_id="PD-001", company="Northwind Systems", role="Software Engineer", kind="full-time",
                    date="2026-11-01", registration_deadline="2026-10-25", min_cgpa=7.0, max_active_backlogs=1,
                    departments="all", venue="Seminar Hall",
                ),
                PlacementDrive(
                    drive_id="PD-002", company="Northwind Systems", role="Software Engineering Intern", kind="internship",
                    date="2026-11-10", registration_deadline="2026-10-30", min_cgpa=6.5, max_active_backlogs=1,
                    departments="all", venue="Student Activity Centre",
                ),
                PlacementDrive(
                    drive_id="PD-003", company="Cobalt Labs", role="Embedded Engineer", kind="internship",
                    date="2026-12-01", registration_deadline="2026-11-20", min_cgpa=9.0, max_active_backlogs=0,
                    departments=["Electronics and Communication Engineering"], venue="Seminar Hall",
                ),
                PlacementDrive(
                    drive_id="PD-004", company="Old Corp", role="Analyst", kind="full-time",
                    date="2026-09-01", registration_deadline="2026-08-20", min_cgpa=6.0, max_active_backlogs=1,
                    departments="all", venue="Seminar Hall",
                ),
            ]
        )
