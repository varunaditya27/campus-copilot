from fastapi import APIRouter, Response

from app.api.deps import SignedInStudent
from app.core.errors import AppError
from app.models.academic import ProfileUpdate, StudentProfileView
from app.services import academic_service, calendar_service

router = APIRouter(prefix="/api/students", tags=["students"])


@router.get("/me/profile")
def get_profile(student: SignedInStudent) -> StudentProfileView:
    profile = academic_service.get_profile(student.student_id)
    if profile is None:
        raise AppError(404, "not_found", "No student record was found.")
    return profile


@router.put("/me/profile")
def update_profile(update: ProfileUpdate, student: SignedInStudent) -> StudentProfileView:
    """Only preferences can be changed here; the rest comes from the student record."""
    profile = academic_service.update_preferences(student.student_id, update.preferences)
    if profile is None:
        raise AppError(404, "not_found", "No student record was found.")
    return profile


@router.get("/me/calendar.ics")
def my_calendar(student: SignedInStudent) -> Response:
    """The events the student is registered for, as a file any calendar app can import."""
    return Response(
        content=calendar_service.registrations_calendar(student.student_id),
        media_type="text/calendar; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="campus-copilot-events.ics"'},
    )
