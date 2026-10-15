from typing import Annotated

from pydantic import Field, validate_call

from app.models.ids import StudentId
from app.services import registration_service


@validate_call
def register_for_event(student_id: StudentId, event_id: Annotated[str, Field(max_length=64)]) -> dict:
    return registration_service.create_registration(student_id, event_id)
