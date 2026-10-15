from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Cookie, Response

from app.agent.agent import run_agent
from app.core.config import COOKIE_SECURE
from app.core.errors import AppError
from app.models.chat import ChatHistoryResponse, ChatRequest, ChatResponse
from app.services import chat_service

router = APIRouter(prefix="/api/chat", tags=["chat"])

SESSION_COOKIE = "session_id"
SESSION_MAX_AGE = 60 * 60 * 24 * 30
# How many of the most recent messages the model gets to see.
HISTORY_WINDOW = 40

SessionCookie = Annotated[str | None, Cookie(alias=SESSION_COOKIE)]


@router.post("")
def chat(request: ChatRequest, response: Response, session_cookie: SessionCookie = None) -> ChatResponse:
    session_id = chat_service.resolve_session(session_cookie)
    history = chat_service.load_history(session_id, HISTORY_WINDOW)
    result = run_agent(request.message, history)
    chat_service.save_exchange(session_id, request.message, result)
    response.set_cookie(
        SESSION_COOKIE,
        str(session_id),
        max_age=SESSION_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=COOKIE_SECURE,
    )
    return result


@router.get("/history")
def history(session_cookie: SessionCookie = None) -> ChatHistoryResponse:
    session_id = chat_service.parse_session_id(session_cookie)
    if session_id is None:
        return ChatHistoryResponse(session_id=None, messages=[])
    return ChatHistoryResponse(session_id=session_id, messages=chat_service.list_messages(session_id))


@router.delete("/sessions/{session_id}", status_code=204)
def delete_session(session_id: UUID, session_cookie: SessionCookie = None) -> Response:
    # A session id only counts as the caller's if their cookie matches it.
    # Anything else is reported as missing, so ids of other sessions stay hidden.
    if session_cookie != str(session_id) or not chat_service.delete_session(session_id):
        raise AppError(404, "not_found", "No such conversation.")
    response = Response(status_code=204)
    response.delete_cookie(SESSION_COOKIE, httponly=True, samesite="lax", secure=COOKIE_SECURE)
    return response
