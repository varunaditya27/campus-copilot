from typing import Annotated

from fastapi import Cookie, Depends

from app.core import security
from app.core.errors import AppError
from app.models.auth import CurrentStudent
from app.services import auth_service

ACCESS_COOKIE = "access_token"


def get_current_student(
    access_token: Annotated[str | None, Cookie(alias=ACCESS_COOKIE)] = None,
) -> CurrentStudent:
    """The signed-in student, or a 401. Reads the access-token cookie."""
    user_id = security.decode_access_token(access_token) if access_token else None
    student = auth_service.get_current_student(user_id) if user_id is not None else None
    if student is None:
        raise AppError(401, "not_authenticated", "Please sign in to continue.")
    return student


SignedInStudent = Annotated[CurrentStudent, Depends(get_current_student)]
