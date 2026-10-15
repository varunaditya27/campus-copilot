from typing import Annotated

from fastapi import Cookie, Depends, Header, Request

from app.core import security
from app.observability import context as observability
from app.security import api_keys, limits
from app.core.errors import AppError
from app.models.auth import CurrentStudent, CurrentUser, Role
from app.services import academic_service, auth_service

ACCESS_COOKIE = "access_token"


def _api_key_user(request: Request, key: str) -> CurrentUser:
    """The administrator an X-Admin-Key stands for. A wrong key is refused, and wrong keys are counted per
    address so they cannot be guessed at speed."""
    ip = request.client.host if request.client else "unknown"
    if not limits.allow("admin-key", ip):
        raise AppError(429, "rate_limited", "Too many attempts. Please wait a moment and try again.")
    key_id = api_keys.verify(key)
    if key_id is None:
        raise AppError(401, "invalid_api_key", "That API key is not valid.")
    observability.bind(role="admin", api_key=key_id)
    return CurrentUser(user_id=0, role="admin", name=f"API key {key_id}", email="")


def get_current_user(
    request: Request,
    access_token: Annotated[str | None, Cookie(alias=ACCESS_COOKIE)] = None,
    admin_key: Annotated[str | None, Header(alias="X-Admin-Key")] = None,
) -> CurrentUser:
    """Whoever is signed in, or a 401. A valid X-Admin-Key header makes the caller an administrator for
    scripts and automation; otherwise the access-token cookie is read."""
    if admin_key is not None:
        return _api_key_user(request, admin_key)
    user_id = security.decode_access_token(access_token) if access_token else None
    user = auth_service.get_current_user(user_id) if user_id is not None else None
    if user is None:
        raise AppError(401, "not_authenticated", "Please sign in to continue.")
    observability.bind(user_id=user.user_id, role=user.role)
    return user


SignedInUser = Annotated[CurrentUser, Depends(get_current_user)]


def forbidden() -> AppError:
    return AppError(403, "forbidden", "You do not have permission to do that.")


def get_current_student(user: SignedInUser) -> CurrentStudent:
    """The signed-in student; any other role gets a 403."""
    if user.role != "student":
        raise forbidden()
    profile = academic_service.get_profile(user.student_id)
    return CurrentStudent(
        user_id=user.user_id,
        student_id=user.student_id,
        name=user.name,
        program=user.program,
        year=user.year,
        email=user.email,
        semester=profile.semester if profile else None,
        section=profile.section if profile else None,
        electives=[e.name for e in profile.electives] if profile else [],
        interests=profile.preferences.interests if profile else [],
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
