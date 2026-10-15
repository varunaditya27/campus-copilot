from typing import Annotated

from fastapi import Cookie, Depends

from app.core import security
from app.core.errors import AppError
from app.models.auth import CurrentStudent, CurrentUser, Role
from app.services import auth_service

ACCESS_COOKIE = "access_token"


def get_current_user(
    access_token: Annotated[str | None, Cookie(alias=ACCESS_COOKIE)] = None,
) -> CurrentUser:
    """Whoever is signed in, or a 401. Reads the access-token cookie."""
    user_id = security.decode_access_token(access_token) if access_token else None
    user = auth_service.get_current_user(user_id) if user_id is not None else None
    if user is None:
        raise AppError(401, "not_authenticated", "Please sign in to continue.")
    return user


SignedInUser = Annotated[CurrentUser, Depends(get_current_user)]


def forbidden() -> AppError:
    return AppError(403, "forbidden", "You do not have permission to do that.")


def get_current_student(user: SignedInUser) -> CurrentStudent:
    """The signed-in student; any other role gets a 403."""
    if user.role != "student":
        raise forbidden()
    return CurrentStudent(
        user_id=user.user_id,
        student_id=user.student_id,
        name=user.name,
        program=user.program,
        year=user.year,
        email=user.email,
    )


SignedInStudent = Annotated[CurrentStudent, Depends(get_current_student)]


def require_roles(*roles: Role):
    """A dependency that lets only the given roles through (403 for the rest)."""

    def check(user: SignedInUser) -> CurrentUser:
        if user.role not in roles:
            raise forbidden()
        return user

    return Depends(check)


AdminUser = Annotated[CurrentUser, require_roles("admin")]
# Admins can do everything the other staff roles can.
StaffUser = Annotated[CurrentUser, require_roles("staff", "admin")]
EventEditor = Annotated[CurrentUser, require_roles("faculty", "admin")]
