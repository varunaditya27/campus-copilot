from typing import Literal

from pydantic import BaseModel

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
