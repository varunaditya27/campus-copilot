from fastapi import APIRouter
from pydantic import BaseModel

from app.services import registration_service

router = APIRouter(prefix="/api/register", tags=["registration"])


class RegisterRequest(BaseModel):
    event_id: str
    student_id: str


class RegisterResponse(BaseModel):
    success: bool
    registration_id: str | None = None
    error: str | None = None


@router.post("")
def register(request: RegisterRequest) -> RegisterResponse:
    result = registration_service.create_registration(request.student_id, request.event_id)
    return RegisterResponse(**result)
