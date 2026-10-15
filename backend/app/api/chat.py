import json
from collections.abc import Iterator
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Cookie, Response
from fastapi.responses import StreamingResponse

from app.agent.supervisor import run_agent, run_agent_stream
from app.api.deps import SignedInStudent
from app.core.config import COOKIE_SECURE
from app.core.errors import AppError
from app.models.chat import (
    ChatHistoryResponse,
    ChatRequest,
    ChatResponse,
    ConversationSummary,
    SessionSummary,
)
from app.services import chat_service, entity_service, summary_service, usage_service

router = APIRouter(prefix="/api/chat", tags=["chat"])

SESSION_COOKIE = "session_id"
SESSION_MAX_AGE = 60 * 60 * 24 * 30
# How many of the most recent messages the model gets to see.
HISTORY_WINDOW = 40

# Remembers which of the student's conversations the browser is in.
SessionCookie = Annotated[str | None, Cookie(alias=SESSION_COOKIE)]


def _set_session_cookie(response: Response, session_id: UUID) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        str(session_id),
        max_age=SESSION_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=COOKIE_SECURE,
    )


@router.post("")
def chat(
    request: ChatRequest,
    response: Response,
    student: SignedInStudent,
    session_cookie: SessionCookie = None,
) -> ChatResponse:
    session_id = chat_service.resolve_session(session_cookie, student.student_id)
    history = chat_service.load_history(session_id, HISTORY_WINDOW)
    result = run_agent(request.message, history, student, entity_service.recent(session_id))
    chat_service.save_exchange(session_id, request.message, result)
    entity_service.remember_exchange(session_id, request.message, result.reply, student.program)
    usage_service.record_exchange(student.student_id, session_id, request.message, result)
    _set_session_cookie(response, session_id)
    return result


def _sse(event: dict) -> str:
    # One server-sent event: a "data:" line holding JSON, ended by a blank line.
    return f"data: {json.dumps(event)}\n\n"


@router.post("/stream")
def chat_stream(
    request: ChatRequest, student: SignedInStudent, session_cookie: SessionCookie = None
) -> StreamingResponse:
    """Same as POST /api/chat, but streamed as server-sent events.

    Once streaming has begun the HTTP status is already 200, so failures are
    reported as an "error" event instead.
    """
    session_id = chat_service.resolve_session(session_cookie, student.student_id)
    history = chat_service.load_history(session_id, HISTORY_WINDOW)
    entities = entity_service.recent(session_id)

    def events() -> Iterator[str]:
        try:
            for event in run_agent_stream(request.message, history, student, entities):
                if event["type"] == "done":
                    done = ChatResponse.model_validate(event["payload"])
                    chat_service.save_exchange(session_id, request.message, done)
                    entity_service.remember_exchange(session_id, request.message, done.reply, student.program)
                    usage_service.record_exchange(student.student_id, session_id, request.message, done)
                yield _sse(event)
        except AppError as exc:
            yield _sse(
                {"type": "error", "payload": {"error_code": exc.error_code, "message": exc.message}}
            )
        except Exception:
            yield _sse(
                {
                    "type": "error",
                    "payload": {
                        "error_code": "internal_error",
                        "message": "Something went wrong on our side. Please try again.",
                    },
                }
            )

    response = StreamingResponse(
        events(),
        media_type="text/event-stream",
        # no-cache: never reuse a stale stream. X-Accel-Buffering: tell nginx
        # not to hold the events back until the response ends.
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
    _set_session_cookie(response, session_id)
    return response


@router.get("/history")
def history(student: SignedInStudent, session_cookie: SessionCookie = None) -> ChatHistoryResponse:
    session_id = chat_service.find_owned_session(session_cookie, student.student_id)
    if session_id is None:
        return ChatHistoryResponse(session_id=None, messages=[])
    return ChatHistoryResponse(session_id=session_id, messages=chat_service.list_messages(session_id))


@router.get("/sessions")
def sessions(student: SignedInStudent) -> list[SessionSummary]:
    return chat_service.list_sessions(student.student_id)


@router.get("/sessions/{session_id}/summary")
def summary(session_id: UUID, student: SignedInStudent) -> ConversationSummary:
    """Two or three sentences on what a conversation was about. The first request
    asks the model; later ones are answered from the saved summary until the
    conversation grows."""
    return summary_service.summarize(session_id, student.student_id)


@router.delete("/sessions/{session_id}", status_code=204)
def delete_session(session_id: UUID, student: SignedInStudent) -> Response:
    # Someone else's session is reported as missing, so its id is not confirmed.
    if not chat_service.delete_session(session_id, student.student_id):
        raise AppError(404, "not_found", "No such conversation.")
    response = Response(status_code=204)
    response.delete_cookie(SESSION_COOKIE, httponly=True, samesite="lax", secure=COOKIE_SECURE)
    return response
