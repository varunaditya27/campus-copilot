from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import delete, select, update

from app.db import session as db_session
from app.db.models import ChatMessage, ChatSession, ConversationEntity
from app.models.chat import ChatHistoryItem, ChatResponse, SessionSummary, StoredMessage

PREVIEW_CHARS = 80


def parse_session_id(raw: str | None) -> UUID | None:
    try:
        return UUID(raw) if raw else None
    except ValueError:
        return None


def find_owned_session(raw_id: str | None, student_id: str) -> UUID | None:
    """The session id if it exists and belongs to this student, else None."""
    session_id = parse_session_id(raw_id)
    if session_id is None:
        return None
    with db_session.SessionLocal() as db:
        return db.scalar(
            select(ChatSession.session_id).where(
                ChatSession.session_id == session_id, ChatSession.student_id == student_id
            )
        )


def resolve_session(raw_id: str | None, student_id: str) -> UUID:
    """The student's existing session, or a new one if the id is missing,
    malformed, unknown, or belongs to someone else."""
    existing = find_owned_session(raw_id, student_id)
    if existing is not None:
        return existing
    with db_session.SessionLocal() as db:
        chat_session = ChatSession(student_id=student_id)
        db.add(chat_session)
        db.commit()
        return chat_session.session_id


def load_history(session_id: UUID, limit: int) -> list[ChatHistoryItem]:
    with db_session.SessionLocal() as db:
        rows = db.scalars(
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.id.desc())
            .limit(limit)
        ).all()
    return [ChatHistoryItem(role=row.role, content=row.content) for row in reversed(rows)]


def save_exchange(session_id: UUID, user_message: str, response: ChatResponse) -> None:
    with db_session.SessionLocal() as db:
        db.add(ChatMessage(session_id=session_id, role="user", content=user_message))
        db.add(
            ChatMessage(
                session_id=session_id,
                role="assistant",
                content=response.reply,
                tool_activity=[t.model_dump() for t in response.toolActivity]
                if response.toolActivity
                else None,
                sources=[s.model_dump() for s in response.sources] if response.sources else None,
            )
        )
        db.execute(
            update(ChatSession)
            .where(ChatSession.session_id == session_id)
            .values(updated_at=datetime.now(timezone.utc))
        )
        db.commit()


def list_messages(session_id: UUID) -> list[StoredMessage]:
    with db_session.SessionLocal() as db:
        rows = db.scalars(
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.id)
        ).all()
    return [
        StoredMessage(
            id=row.id,
            role=row.role,
            content=row.content,
            toolActivity=row.tool_activity,
            sources=row.sources,
            createdAt=row.created_at,
        )
        for row in rows
    ]


def list_sessions(student_id: str) -> list[SessionSummary]:
    """The student's conversations, most recently active first."""
    first_question = (
        select(ChatMessage.content)
        .where(ChatMessage.session_id == ChatSession.session_id, ChatMessage.role == "user")
        .order_by(ChatMessage.id)
        .limit(1)
        .scalar_subquery()
    )
    with db_session.SessionLocal() as db:
        rows = db.execute(
            select(ChatSession, first_question)
            .where(ChatSession.student_id == student_id)
            .order_by(ChatSession.updated_at.desc(), ChatSession.created_at.desc())
        ).all()
    return [
        SessionSummary(
            session_id=chat_session.session_id,
            createdAt=chat_session.created_at,
            updatedAt=chat_session.updated_at,
            preview=question[:PREVIEW_CHARS] if question else None,
        )
        for chat_session, question in rows
    ]


def delete_session(session_id: UUID, student_id: str) -> bool:
    """Delete a conversation the student owns. False if it is not theirs."""
    with db_session.SessionLocal() as db:
        owned = db.scalar(
            select(ChatSession.session_id).where(
                ChatSession.session_id == session_id, ChatSession.student_id == student_id
            )
        )
        if owned is None:
            return False
        db.execute(delete(ConversationEntity).where(ConversationEntity.session_id == session_id))
        db.execute(delete(ChatMessage).where(ChatMessage.session_id == session_id))
        db.execute(delete(ChatSession).where(ChatSession.session_id == session_id))
        db.commit()
        return True
