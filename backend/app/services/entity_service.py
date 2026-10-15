import logging
import re
from datetime import datetime, timezone
from functools import lru_cache
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from app.core.config import KNOWLEDGE_DIR
from app.db import session as db_session
from app.db.models import ConversationEntity, Course
from app.models.memory import Entity
from app.rag.ingest import knowledge_files
from app.services import event_service

logger = logging.getLogger(__name__)

# How many of each kind the assistant is reminded of.
SHOWN_PER_KIND = 5

_COURSE_CODE = re.compile(r"\b([A-Z]{2}\d{3})\b")
_FACULTY = re.compile(r"\b(Dr|Mr|Ms|Prof)\. ([A-Z][A-Za-z'’]+(?: [A-Z][A-Za-z'’]+)+)")


def _contains(text: str, phrase: str) -> bool:
    """Whether the phrase appears as whole words, ignoring case."""
    return re.search(r"(?<!\w)" + re.escape(phrase.lower()) + r"(?!\w)", text.lower()) is not None


@lru_cache
def faculty_names() -> dict[str, str]:
    """Every faculty member named in the knowledge documents: name -> "Dr. Name"."""
    names: dict[str, str] = {}
    for path in knowledge_files(KNOWLEDGE_DIR):
        for title, name in _FACULTY.findall(path.read_text()):
            names.setdefault(name, f"{title}. {name}")
    return names


def _events_in(text: str) -> list[Entity]:
    found = []
    for event in event_service.list_events():
        short = re.split(r":| - | — ", event.name)[0].strip()
        aliases = [event.id, event.name] + ([short] if len(short) >= 8 else [])
        if any(_contains(text, alias) for alias in aliases):
            found.append(Entity(kind="event", key=event.id, label=event.name))
    return found


def _courses_in(text: str, department: str | None) -> list[Entity]:
    with db_session.SessionLocal() as db:
        courses = list(db.scalars(select(Course)))
    by_code = {c.course_code: c for c in courses}
    found: dict[str, Entity] = {}
    for code in _COURSE_CODE.findall(text):
        if code in by_code:
            found[code] = Entity(kind="course", key=code, label=f"{by_code[code].name} ({code})")
    # A course name is only taken to mean the student's own department's course:
    # "Machine Learning" is taught by two departments.
    if department:
        for course in courses:
            if course.department == department and " " in course.name and _contains(text, course.name):
                found.setdefault(course.course_code, Entity(kind="course", key=course.course_code, label=f"{course.name} ({course.course_code})"))
    return list(found.values())


def _faculty_in(text: str) -> list[Entity]:
    return [
        Entity(kind="faculty", key=name, label=label)
        for name, label in faculty_names().items()
        if _contains(text, name)
    ]


def extract(text: str, department: str | None = None) -> list[Entity]:
    """The events, courses and faculty members a piece of text mentions.

    This looks things up in what the application already knows (the events, the
    course catalogue, the faculty named in the knowledge documents) instead of
    asking a model, so it is instant and can only find real things.
    """
    return _events_in(text) + _courses_in(text, department) + _faculty_in(text)


def remember(session_id: UUID, entities: list[Entity]) -> None:
    """Record that these were mentioned just now in the conversation."""
    now = datetime.now(timezone.utc)
    for entity in dict.fromkeys(entities):
        with db_session.SessionLocal() as db:
            existing = db.scalar(
                select(ConversationEntity).where(
                    ConversationEntity.session_id == session_id,
                    ConversationEntity.kind == entity.kind,
                    ConversationEntity.key == entity.key,
                )
            )
            try:
                if existing:
                    db.execute(
                        update(ConversationEntity)
                        .where(ConversationEntity.id == existing.id)
                        .values(mentions=ConversationEntity.mentions + 1, updated_at=now, label=entity.label)
                    )
                else:
                    db.add(
                        ConversationEntity(
                            session_id=session_id, kind=entity.kind, key=entity.key, label=entity.label, updated_at=now
                        )
                    )
                db.commit()
            except IntegrityError:
                db.rollback()  # another request recorded it at the same moment; nothing is lost


def remember_exchange(session_id: UUID, user_message: str, reply: str, department: str | None) -> None:
    """Remember what an exchange mentioned. Never fails the chat: memory is a convenience."""
    try:
        remember(session_id, extract(f"{user_message}\n{reply}", department))
    except Exception:
        logger.exception("Could not remember what the conversation mentioned")


def recent(session_id: UUID) -> list[Entity]:
    """What the conversation has mentioned, most recently first, a few of each kind."""
    with db_session.SessionLocal() as db:
        rows = db.scalars(
            select(ConversationEntity)
            .where(ConversationEntity.session_id == session_id)
            .order_by(ConversationEntity.updated_at.desc(), ConversationEntity.id.desc())
        ).all()
    counts: dict[str, int] = {}
    chosen = []
    for row in rows:
        counts[row.kind] = counts.get(row.kind, 0) + 1
        if counts[row.kind] <= SHOWN_PER_KIND:
            chosen.append(Entity(kind=row.kind, key=row.key, label=row.label))
    return chosen
