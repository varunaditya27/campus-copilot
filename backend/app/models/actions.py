from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class ConfirmationLine(BaseModel):
    label: str
    value: str


class Confirmation(BaseModel):
    """What the student is shown before something is done for them."""

    action_id: str
    action: str
    title: str
    lines: list[ConfirmationLine]
    expires_at: datetime


class ActionOutcome(BaseModel):
    """What happened when the student approved (or declined) an action."""

    action_id: str
    status: Literal["confirmed", "cancelled", "failed"]
    success: bool
    message: str
    details: dict[str, str] = {}
