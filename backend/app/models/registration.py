from datetime import datetime

from pydantic import BaseModel


class RegistrationRecord(BaseModel):
    """One registration, with the event and student details staff need."""

    registration_id: str
    status: str
    registered_at: datetime
    event_id: str
    event_name: str
    event_date: str
    student_id: str
    student_name: str
    program: str
    year: int
