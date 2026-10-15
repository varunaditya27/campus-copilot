import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    MetaData,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    # Deterministic constraint names, so later migrations can drop or alter
    # them by name on any database.
    metadata = MetaData(
        naming_convention={
            "ix": "ix_%(column_0_label)s",
            "uq": "uq_%(table_name)s_%(column_0_name)s",
            "ck": "ck_%(table_name)s_%(constraint_name)s",
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
            "pk": "pk_%(table_name)s",
        }
    )


class Student(Base):
    __tablename__ = "students"

    student_id: Mapped[str] = mapped_column(String(10), primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    program: Mapped[str] = mapped_column(String(100))
    year: Mapped[int]


class Course(Base):
    __tablename__ = "courses"
    __table_args__ = (
        CheckConstraint("kind IN ('theory', 'lab', 'project', 'elective')", name="valid_kind"),
        CheckConstraint("semester BETWEEN 1 AND 8", name="valid_semester"),
        CheckConstraint("credits > 0", name="positive_credits"),
    )

    course_code: Mapped[str] = mapped_column(String(10), primary_key=True)
    name: Mapped[str] = mapped_column(String(150))
    credits: Mapped[int]
    department: Mapped[str] = mapped_column(String(100))
    semester: Mapped[int]
    kind: Mapped[str] = mapped_column(String(20))


class StudentProfile(Base):
    """What the assistant knows about a student beyond the roster: where they are in
    the degree, and what they have said they are interested in."""

    __tablename__ = "student_profiles"
    __table_args__ = (CheckConstraint("semester BETWEEN 1 AND 8", name="valid_semester"),)

    student_id: Mapped[str] = mapped_column(ForeignKey("students.student_id"), primary_key=True)
    semester: Mapped[int]
    section: Mapped[str | None] = mapped_column(String(2))
    electives: Mapped[list] = mapped_column(JSON, default=list)
    preferences: Mapped[dict] = mapped_column(JSON, default=dict)


class AcademicRecord(Base):
    """One student's attendance and result in one course. The grade stays empty
    until the semester's results are published."""

    __tablename__ = "student_academic_records"
    __table_args__ = (
        UniqueConstraint("student_id", "course_code", name="uq_student_academic_records_student_course"),
        CheckConstraint("attended >= 0 AND attended <= total", name="attended_within_total"),
        CheckConstraint(
            "grade IS NULL OR grade IN ('O', 'A+', 'A', 'B+', 'B', 'C', 'P', 'F')", name="valid_grade"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[str] = mapped_column(ForeignKey("students.student_id"), index=True)
    course_code: Mapped[str] = mapped_column(ForeignKey("courses.course_code"))
    semester: Mapped[int]
    attended: Mapped[int]
    total: Mapped[int]
    grade: Mapped[str | None] = mapped_column(String(2))


class FacultyMember(Base):
    """The public faculty directory. Separate from `faculty`, which holds the
    accounts of faculty who can sign in."""

    __tablename__ = "faculty_members"

    faculty_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), index=True)
    designation: Mapped[str] = mapped_column(String(50))
    department: Mapped[str] = mapped_column(String(100))
    specialisation: Mapped[str | None] = mapped_column(String(200))
    leadership_role: Mapped[str | None] = mapped_column(String(100))
    office: Mapped[str | None] = mapped_column(String(100))
    office_hours: Mapped[str | None] = mapped_column(String(200))
    email: Mapped[str] = mapped_column(String(254))


class CourseOffering(Base):
    """Who teaches a course this semester, and how many hours a week it takes."""

    __tablename__ = "course_offerings"

    course_code: Mapped[str] = mapped_column(ForeignKey("courses.course_code"), primary_key=True)
    faculty_id: Mapped[str] = mapped_column(ForeignKey("faculty_members.faculty_id"), index=True)
    lecture_hours: Mapped[int]
    practical_hours: Mapped[int]


class TimetableSlot(Base):
    """One class in a class group's week. `day` counts from Monday = 0."""

    __tablename__ = "timetable_slots"

    id: Mapped[int] = mapped_column(primary_key=True)
    department: Mapped[str] = mapped_column(String(100))
    semester: Mapped[int]
    section: Mapped[str] = mapped_column(String(2))
    day: Mapped[int]
    start: Mapped[str] = mapped_column(String(5))
    end: Mapped[str] = mapped_column(String(5))
    course_code: Mapped[str] = mapped_column(ForeignKey("courses.course_code"))
    room: Mapped[str] = mapped_column(String(100))

    __table_args__ = (
        CheckConstraint("day BETWEEN 0 AND 6", name="valid_day"),
        Index("ix_timetable_slots_group", "department", "semester", "section", "day"),
    )


class Exam(Base):
    __tablename__ = "exams"
    __table_args__ = (
        CheckConstraint(
            "exam_type IN ('internal', 'end-semester', 'practical', 'project-review')", name="valid_exam_type"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    course_code: Mapped[str] = mapped_column(ForeignKey("courses.course_code"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    exam_type: Mapped[str] = mapped_column(String(20))
    date: Mapped[str] = mapped_column(String(10))
    start_time: Mapped[str] = mapped_column(String(5))
    duration_minutes: Mapped[int]
    venue: Mapped[str] = mapped_column(String(100))


class FeeRecord(Base):
    """One fee component a student owes for a term, and how much of it is paid."""

    __tablename__ = "fee_records"
    __table_args__ = (
        UniqueConstraint("student_id", "term", "component", name="uq_fee_records_student_term_component"),
        CheckConstraint("paid_amount >= 0 AND paid_amount <= amount", name="paid_within_amount"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[str] = mapped_column(ForeignKey("students.student_id"), index=True)
    term: Mapped[str] = mapped_column(String(20))
    component: Mapped[str] = mapped_column(String(50))
    amount: Mapped[int]
    due_date: Mapped[str] = mapped_column(String(10))
    paid_amount: Mapped[int] = mapped_column(default=0)
    paid_on: Mapped[str | None] = mapped_column(String(10))


class Book(Base):
    __tablename__ = "books"

    book_id: Mapped[str] = mapped_column(String(10), primary_key=True)
    title: Mapped[str] = mapped_column(String(250), index=True)
    author: Mapped[str] = mapped_column(String(250))
    isbn: Mapped[str] = mapped_column(String(30), unique=True)
    category: Mapped[str] = mapped_column(String(50))
    shelf_location: Mapped[str] = mapped_column(String(100))
    copies_total: Mapped[int]
    reference_only: Mapped[bool] = mapped_column(default=False)


class BookLoan(Base):
    """A copy that is out. A returned book has no row."""

    __tablename__ = "book_loans"

    id: Mapped[int] = mapped_column(primary_key=True)
    book_id: Mapped[str] = mapped_column(ForeignKey("books.book_id"), index=True)
    student_id: Mapped[str] = mapped_column(ForeignKey("students.student_id"), index=True)
    borrowed_on: Mapped[str] = mapped_column(String(10))
    due_date: Mapped[str] = mapped_column(String(10))


class BookReservation(Base):
    """A hold: the student is waiting for a copy of a title that has none on the shelf."""

    __tablename__ = "book_reservations"
    __table_args__ = (UniqueConstraint("book_id", "student_id", name="uq_book_reservations_book_student"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    book_id: Mapped[str] = mapped_column(ForeignKey("books.book_id"), index=True)
    student_id: Mapped[str] = mapped_column(ForeignKey("students.student_id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class CanteenItem(Base):
    __tablename__ = "canteen_menu"
    __table_args__ = (
        CheckConstraint("weekday BETWEEN 0 AND 6", name="valid_weekday"),
        CheckConstraint("meal IN ('breakfast', 'lunch', 'evening', 'dinner')", name="valid_meal"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    weekday: Mapped[int]
    meal: Mapped[str] = mapped_column(String(20))
    item: Mapped[str] = mapped_column(String(150))
    price: Mapped[int]
    vegetarian: Mapped[bool]


class StudyRoom(Base):
    __tablename__ = "study_rooms"

    room_id: Mapped[str] = mapped_column(String(10), primary_key=True)
    name: Mapped[str] = mapped_column(String(50))
    capacity: Mapped[int]
    floor: Mapped[int]


class RoomBooking(Base):
    __tablename__ = "room_bookings"
    __table_args__ = (UniqueConstraint("room_id", "date", "start", name="uq_room_bookings_room_date_start"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    room_id: Mapped[str] = mapped_column(ForeignKey("study_rooms.room_id"))
    student_id: Mapped[str] = mapped_column(ForeignKey("students.student_id"), index=True)
    date: Mapped[str] = mapped_column(String(10))
    start: Mapped[str] = mapped_column(String(5))
    end: Mapped[str] = mapped_column(String(5))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class BusRoute(Base):
    __tablename__ = "bus_routes"

    route_code: Mapped[str] = mapped_column(String(10), primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    stops: Mapped[list] = mapped_column(JSON)
    service: Mapped[list] = mapped_column(JSON)  # windows with a frequency, or fixed departures
    notes: Mapped[str] = mapped_column(Text)


class LostFoundItem(Base):
    __tablename__ = "lost_found_items"
    __table_args__ = (CheckConstraint("status IN ('unclaimed', 'claimed')", name="valid_status"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    description: Mapped[str] = mapped_column(String(300))
    location_found: Mapped[str] = mapped_column(String(200))
    found_on: Mapped[str] = mapped_column(String(10))
    status: Mapped[str] = mapped_column(String(20), default="unclaimed")
    reported_by: Mapped[str | None] = mapped_column(ForeignKey("students.student_id"))


class MaintenanceRequest(Base):
    __tablename__ = "maintenance_requests"
    __table_args__ = (
        CheckConstraint("status IN ('open', 'in_progress', 'resolved')", name="valid_status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[str] = mapped_column(ForeignKey("students.student_id"), index=True)
    location: Mapped[str] = mapped_column(String(200))
    category: Mapped[str] = mapped_column(String(30))
    description: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="open")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class GrievanceTicket(Base):
    __tablename__ = "grievance_tickets"
    __table_args__ = (
        CheckConstraint("status IN ('open', 'in_progress', 'resolved')", name="valid_status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[str] = mapped_column(ForeignKey("students.student_id"), index=True)
    category: Mapped[str] = mapped_column(String(30))
    description: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="open", index=True)
    resolution_note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)


class CounsellingSlot(Base):
    """An appointment slot at the Student Counselling Centre. It is taken once `booked_by` is set."""

    __tablename__ = "counselling_slots"

    id: Mapped[int] = mapped_column(primary_key=True)
    date: Mapped[str] = mapped_column(String(10), index=True)
    start: Mapped[str] = mapped_column(String(5))
    end: Mapped[str] = mapped_column(String(5))
    booked_by: Mapped[str | None] = mapped_column(ForeignKey("students.student_id"))


class PlacementDrive(Base):
    __tablename__ = "placement_drives"
    __table_args__ = (CheckConstraint("kind IN ('full-time', 'internship')", name="valid_kind"),)

    drive_id: Mapped[str] = mapped_column(String(10), primary_key=True)
    company: Mapped[str] = mapped_column(String(100))
    role: Mapped[str] = mapped_column(String(100))
    kind: Mapped[str] = mapped_column(String(20))
    date: Mapped[str] = mapped_column(String(10))
    registration_deadline: Mapped[str] = mapped_column(String(10))
    min_cgpa: Mapped[float]
    max_active_backlogs: Mapped[int]
    departments: Mapped[list | str] = mapped_column(JSON)  # "all" or a list of department names
    venue: Mapped[str] = mapped_column(String(100))


class Event(Base):
    __tablename__ = "events"
    __table_args__ = (
        CheckConstraint(
            "registered >= 0 AND registered <= capacity",
            name="registered_within_capacity",
        ),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    category: Mapped[str] = mapped_column(String(50))
    date: Mapped[str] = mapped_column(String(10))
    time: Mapped[str] = mapped_column(String(5))
    duration_minutes: Mapped[int]
    venue: Mapped[str] = mapped_column(String(200))
    capacity: Mapped[int]
    registered: Mapped[int] = mapped_column(default=0)
    organizer: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)
    tags: Mapped[list[str]] = mapped_column(JSON)
    # The department that owns the event; faculty may only edit their own.
    department: Mapped[str | None] = mapped_column(String(100))


class Registration(Base):
    __tablename__ = "registrations"
    __table_args__ = (
        UniqueConstraint("student_id", "event_id", name="uq_registrations_student_event"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    registration_id: Mapped[str] = mapped_column(String(40), unique=True)
    student_id: Mapped[str] = mapped_column(ForeignKey("students.student_id"))
    event_id: Mapped[str] = mapped_column(ForeignKey("events.id"), index=True)
    registered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), default="confirmed")


ROLES = ("student", "faculty", "staff", "admin")


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "role IN ('student', 'faculty', 'staff', 'admin')", name="valid_role"
        ),
        # Students are linked to the roster; nobody else is.
        CheckConstraint(
            "(role = 'student' AND student_id IS NOT NULL) "
            "OR (role <> 'student' AND student_id IS NULL)",
            name="student_link",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    role: Mapped[str] = mapped_column(String(20), default="student", server_default="student")
    name: Mapped[str] = mapped_column(String(100))
    student_id: Mapped[str | None] = mapped_column(ForeignKey("students.student_id"), unique=True)
    email: Mapped[str] = mapped_column(String(254), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Faculty(Base):
    __tablename__ = "faculty"

    faculty_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True
    )
    department: Mapped[str] = mapped_column(String(100))
    office: Mapped[str | None] = mapped_column(String(100))
    office_hours: Mapped[str | None] = mapped_column(String(200))


class RefreshToken(Base):
    """One issued refresh token. Only a hash of the token is stored.

    Every login starts a family; each refresh replaces the token with a new
    one in the same family, so a stolen, already-used token can be spotted and
    the whole family revoked.
    """

    __tablename__ = "refresh_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    family_id: Mapped[uuid.UUID] = mapped_column(Uuid, index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class ChatSession(Base):
    __tablename__ = "sessions"

    session_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    # Stays empty until students can sign in (roadmap phase 2).
    student_id: Mapped[str | None] = mapped_column(ForeignKey("students.student_id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    # A short summary of the conversation, and the last message it covers, so it
    # is only written again when the conversation has grown.
    summary: Mapped[str | None] = mapped_column(Text)
    summary_through_message_id: Mapped[int | None]


class ChatMessage(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sessions.session_id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(20))
    content: Mapped[str] = mapped_column(Text)
    tool_activity: Mapped[list | None] = mapped_column(JSON(none_as_null=True))
    sources: Mapped[list | None] = mapped_column(JSON(none_as_null=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class ConversationEntity(Base):
    """Something a conversation has talked about (an event, a course, a faculty
    member), remembered so a later "register me for it" knows what "it" is."""

    __tablename__ = "conversation_entities"
    __table_args__ = (
        UniqueConstraint("session_id", "kind", "key", name="uq_conversation_entities_session_kind_key"),
        CheckConstraint("kind IN ('event', 'course', 'faculty')", name="valid_kind"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sessions.session_id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(20))
    key: Mapped[str] = mapped_column(String(100))  # event id, course code, or faculty name
    label: Mapped[str] = mapped_column(String(200))  # how to show it
    mentions: Mapped[int] = mapped_column(default=1)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class PendingAction(Base):
    """Something the assistant proposed to do for a student, waiting for them to
    approve it. The parameters are kept here, not in the browser, so what the
    student approves is exactly what runs."""

    __tablename__ = "pending_actions"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'confirmed', 'cancelled', 'expired', 'failed')", name="valid_status"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    student_id: Mapped[str] = mapped_column(ForeignKey("students.student_id"), index=True)
    action: Mapped[str] = mapped_column(String(50))
    params: Mapped[dict] = mapped_column(JSON)
    title: Mapped[str] = mapped_column(String(200))
    lines: Mapped[list] = mapped_column(JSON)  # [{"label": ..., "value": ...}] shown on the confirmation card
    status: Mapped[str] = mapped_column(String(20), default="pending")
    result: Mapped[dict | None] = mapped_column(JSON(none_as_null=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
