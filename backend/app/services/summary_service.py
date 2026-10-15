from uuid import UUID

from app.agent.agent import complete_text
from app.core.errors import AppError
from app.db import session as db_session
from app.db.models import ChatSession
from app.models.chat import ConversationSummary
from app.services import chat_service

SUMMARY_PROMPT = (
    "Summarise this conversation between a student and a campus assistant in two or "
    "three short sentences. Say what the student asked about and what was settled or "
    "left open. Write plain sentences: no greeting, no bullet points, no quotation of "
    "the conversation."
)

# A long conversation is summarised from its most recent messages, each trimmed.
MAX_MESSAGES = 60
MAX_CHARS_PER_MESSAGE = 600
MAX_SUMMARY_CHARS = 700


def _transcript(messages) -> str:
    lines = []
    for message in messages[-MAX_MESSAGES:]:
        speaker = "Student" if message.role == "user" else "Assistant"
        lines.append(f"{speaker}: {message.content[:MAX_CHARS_PER_MESSAGE]}")
    return "\n".join(lines)


def summarize(session_id: UUID, student_id: str) -> ConversationSummary:
    """A short summary of one of the student's conversations. The model is asked
    only when the conversation has grown since the last summary."""
    if chat_service.find_owned_session(str(session_id), student_id) is None:
        raise AppError(404, "not_found", "No such conversation.")
    messages = chat_service.list_messages(session_id)
    if not messages:
        raise AppError(422, "empty_conversation", "There is nothing to summarise yet.")
    last_id = messages[-1].id

    with db_session.SessionLocal() as db:
        row = db.get(ChatSession, session_id)
        if row.summary and row.summary_through_message_id == last_id:
            return ConversationSummary(
                session_id=session_id, summary=row.summary, messageCount=len(messages), cached=True
            )

    text = complete_text(
        [{"role": "system", "content": SUMMARY_PROMPT}, {"role": "user", "content": _transcript(messages)}]
    ).strip()[:MAX_SUMMARY_CHARS]
    if not text:
        raise AppError(502, "llm_unavailable", "The AI service did not produce a summary. Please try again.")

    with db_session.SessionLocal() as db:
        row = db.get(ChatSession, session_id)
        row.summary, row.summary_through_message_id = text, last_id
        db.commit()
    return ConversationSummary(session_id=session_id, summary=text, messageCount=len(messages), cached=False)
