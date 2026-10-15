from pydantic import Field, validate_call

from app.models.ids import StudentId
from app.services import campus_service, library_service, placement_service, study_room_service, support_service


@validate_call
def check_library_availability(query: str = Field(min_length=1, max_length=150)) -> dict:
    """Whether a book is available, where it is shelved, and when a copy is due back."""
    return library_service.availability(query)


@validate_call
def get_canteen_menu(day: str | None = Field(default=None, max_length=20)) -> dict:
    """The Central Cafeteria menu for a day."""
    return campus_service.canteen_menu(day)


@validate_call
def get_bus_schedule(route: str | None = Field(default=None, max_length=40)) -> dict:
    """Shuttle routes, stops and the next departures."""
    return campus_service.bus_schedule(route)


@validate_call
def get_lost_and_found(keyword: str = Field(min_length=1, max_length=60)) -> dict:
    """Search the lost and found list."""
    return campus_service.lost_and_found(keyword)


@validate_call
def check_study_room_availability(
    day: str | None = Field(default=None, max_length=20), min_capacity: int | None = Field(default=None, ge=1, le=20)
) -> dict:
    """Free discussion-room slots on a date."""
    return study_room_service.availability(day, min_capacity)


@validate_call
def get_grievance_status(student_id: StudentId, ticket_id: str | None = Field(default=None, max_length=20)) -> dict:
    """The signed-in student's own grievance tickets. The student id is supplied by the agent."""
    return support_service.grievance_status(student_id, ticket_id)


@validate_call
def get_counselling_slots(student_id: StudentId) -> dict:
    """Free counselling slots and the student's own appointment. The student id is supplied by the agent."""
    return support_service.counselling_slots(student_id)


@validate_call
def get_placement_drives(
    company: str | None = Field(default=None, max_length=100),
    from_date: str | None = Field(default=None, max_length=10),
    to_date: str | None = Field(default=None, max_length=10),
) -> dict:
    """Upcoming placement drives with their eligibility criteria."""
    return placement_service.drives(company, from_date, to_date)


@validate_call
def check_placement_eligibility(student_id: StudentId, drive: str = Field(min_length=1, max_length=100)) -> dict:
    """Whether the signed-in student meets a drive's criteria. The student id is supplied by the agent."""
    return placement_service.eligibility(student_id, drive)
