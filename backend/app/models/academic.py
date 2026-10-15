from typing import Annotated

from pydantic import BaseModel, Field, field_validator

from app.models.events import EventCategory


class ElectiveInfo(BaseModel):
    course_code: str
    name: str
    credits: int


class Preferences(BaseModel):
    interests: Annotated[list[EventCategory], Field(max_length=6)] = Field(default_factory=list)

    @field_validator("interests")
    @classmethod
    def _no_repeats(cls, value: list[str]) -> list[str]:
        return list(dict.fromkeys(value))


class ProfileUpdate(BaseModel):
    """What a student may change about their own profile."""

    preferences: Preferences


class StudentProfileView(BaseModel):
    student_id: str
    name: str
    program: str
    year: int
    semester: int
    section: str | None
    electives: list[ElectiveInfo]
    preferences: Preferences
