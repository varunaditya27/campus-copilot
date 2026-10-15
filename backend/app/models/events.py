import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints, field_validator

EventCategory = Literal[
    "artificial-intelligence",
    "web-development",
    "competitive-programming",
    "cybersecurity",
    "research",
    "robotics",
]


class CampusEvent(BaseModel):
    id: str
    name: str
    category: EventCategory
    date: str
    time: str
    duration_minutes: int
    venue: str
    capacity: int
    registered: int
    organizer: str
    description: str
    tags: list[str]
    department: str | None = None


_Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]


class EventInput(BaseModel):
    """What a faculty member or admin supplies to create or edit an event."""

    name: _Text
    category: EventCategory
    date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    time: str = Field(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    duration_minutes: int = Field(ge=1, le=24 * 60)
    venue: _Text
    capacity: int = Field(ge=1, le=100_000)
    organizer: _Text
    description: str = Field(min_length=1, max_length=5000)
    tags: list[Annotated[str, StringConstraints(min_length=1, max_length=50)]] = Field(
        default_factory=list, max_length=20
    )
    # Only an admin can set this; a faculty member's events always carry their own.
    department: str | None = Field(default=None, max_length=100)

    @field_validator("date")
    @classmethod
    def _is_a_real_date(cls, value: str) -> str:
        try:
            datetime.date.fromisoformat(value)
        except ValueError:
            raise ValueError("must be a real calendar date (YYYY-MM-DD)")
        return value
