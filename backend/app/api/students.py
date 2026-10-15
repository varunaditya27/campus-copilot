from fastapi import APIRouter

from app.api.deps import SignedInStudent
from app.core.errors import AppError
from app.models.academic import ProfileUpdate, StudentProfileView
from app.services import academic_service

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
