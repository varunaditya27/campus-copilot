from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import delete, select, update

from app.db import session as db_session
from app.db.models import ChatMessage, ChatSession
from app.models.chat import ChatHistoryItem, ChatResponse, StoredMessage


def parse_session_id(raw: str | None) -> UUID | None:
    try:
        return UUID(raw) if raw else None
    except ValueError:
        return None


def resolve_session(raw_id: str | None) -> UUID:
    """The caller's existing session, or a new one if the id is missing,
    malformed or unknown."""
    session_id = parse_session_id(raw_id)
    with db_session.SessionLocal() as db:
        if session_id is not None and db.get(ChatSession, session_id) is not None:
            return session_id
        chat_session = ChatSession()
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


def delete_session(session_id: UUID) -> bool:
    with db_session.SessionLocal() as db:
        db.execute(delete(ChatMessage).where(ChatMessage.session_id == session_id))
        deleted = db.execute(delete(ChatSession).where(ChatSession.session_id == session_id))
        db.commit()
        return deleted.rowcount > 0
