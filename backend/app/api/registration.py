from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.api.deps import SignedInStudent
from app.services import registration_service

router = APIRouter(prefix="/api/register", tags=["registration"])


class RegisterRequest(BaseModel):
    event_id: str = Field(max_length=64)


class RegisterResponse(BaseModel):
    success: bool
    registration_id: str | None = None
    error: str | None = None


@router.post("")
def register(request: RegisterRequest, student: SignedInStudent) -> RegisterResponse:
    # Always the signed-in student: the client does not get to name one.
    result = registration_service.create_registration(student.student_id, request.event_id)
    return RegisterResponse(**result)
