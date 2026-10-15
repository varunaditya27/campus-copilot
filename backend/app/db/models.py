import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
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
