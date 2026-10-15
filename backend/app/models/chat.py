from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.actions import Confirmation

ChatRole = Literal["user", "assistant"]

# Bound on what a client may send, so one request cannot carry an
# arbitrarily large prompt to the LLM.
MAX_MESSAGE_CHARS = 2000


class ChatHistoryItem(BaseModel):
    role: ChatRole
    content: str


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=MAX_MESSAGE_CHARS)
    # How capable (and slow) a model to use. Left out, ordinary questions use "balanced" and
    # multi-step tasks use "best".
    quality: Literal["fast", "balanced", "best"] | None = None


class Source(BaseModel):
    document: str
    section: str | None = None
    snippet: str | None = None


class ToolActivityEntry(BaseModel):
    id: str
    tool: str
    label: str
    status: Literal["running", "done", "error"]
    resultSummary: str | None = None


class ChatResponse(BaseModel):
    reply: str
    sources: list[Source] | None = None
    toolActivity: list[ToolActivityEntry] | None = None
    confirmation: Confirmation | None = None


class StoredMessage(BaseModel):
    id: int
    role: ChatRole
    content: str
    toolActivity: list[ToolActivityEntry] | None = None
    sources: list[Source] | None = None
    createdAt: datetime


class SessionSummary(BaseModel):
    session_id: UUID
    createdAt: datetime
    updatedAt: datetime
    preview: str | None


class ConversationSummary(BaseModel):
    session_id: UUID
    summary: str
    messageCount: int
    cached: bool  # True if the summary was written earlier and nothing has been said since


class ChatHistoryResponse(BaseModel):
    session_id: UUID | None
    messages: list[StoredMessage]
