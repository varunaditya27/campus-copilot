from typing import Literal

from pydantic import BaseModel

EntityKind = Literal["event", "course", "faculty"]


class Entity(BaseModel, frozen=True):
    """Something a conversation has mentioned, with the key a tool would need."""

    kind: EntityKind
    key: str  # an event id, a course code, or a faculty member's name
    label: str  # how to show it
