from typing import Literal

from pydantic import BaseModel

ChatRole = Literal["user", "assistant"]


class ChatHistoryItem(BaseModel):
    role: ChatRole
    content: str


class ChatRequest(BaseModel):
    message: str
    history: list[ChatHistoryItem] = []


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


class ConfirmationEvent(BaseModel):
    id: str
    name: str
    date: str
    time: str
    venue: str


class RegistrationConfirmation(BaseModel):
    event: ConfirmationEvent
    studentId: str


class ChatResponse(BaseModel):
    reply: str
    sources: list[Source] | None = None
    toolActivity: list[ToolActivityEntry] | None = None
    confirmation: RegistrationConfirmation | None = None
