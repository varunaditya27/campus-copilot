from pydantic import Field, validate_call

from app.models.ids import StudentId
from app.services import engagement_service


@validate_call
def get_event_detail(student_id: StudentId, event_id: str = Field(min_length=1, max_length=64)) -> dict:
    """Full details of one event and the signed-in student's status in it. The student id is supplied by the agent."""
    return engagement_service.event_detail(student_id, event_id)


@validate_call
def get_my_registrations(student_id: StudentId) -> dict:
    """The signed-in student's registrations and waitlist places. The student id is supplied by the agent."""
    return engagement_service.my_registrations(student_id)


@validate_call
def get_event_feedback_form(student_id: StudentId, event_id: str = Field(min_length=1, max_length=64)) -> dict:
    """The feedback form for an event and whether the signed-in student can fill it in. The student id is supplied by the agent."""
    return engagement_service.feedback_form(student_id, event_id)
