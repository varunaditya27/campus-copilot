from typing import Annotated

from fastapi import APIRouter, Cookie, Response

from app.api.deps import ACCESS_COOKIE, SignedInStudent
from app.core.config import ACCESS_TOKEN_MINUTES, COOKIE_SECURE, REFRESH_TOKEN_DAYS
from app.core.errors import AppError
from app.models.auth import CurrentStudent, LoginRequest, RegisterRequest
from app.services import auth_service

router = APIRouter(prefix="/api/auth", tags=["auth"])

REFRESH_COOKIE = "refresh_token"
# The refresh cookie is only ever sent to the auth endpoints.
REFRESH_COOKIE_PATH = "/api/auth"


def _set_auth_cookies(response: Response, access: str, refresh: str) -> None:
    response.set_cookie(
        ACCESS_COOKIE,
        access,
        max_age=ACCESS_TOKEN_MINUTES * 60,
        httponly=True,
        samesite="lax",
        secure=COOKIE_SECURE,
    )
    response.set_cookie(
        REFRESH_COOKIE,
        refresh,
        max_age=REFRESH_TOKEN_DAYS * 24 * 60 * 60,
        path=REFRESH_COOKIE_PATH,
        httponly=True,
        samesite="strict",
        secure=COOKIE_SECURE,
    )


def _clear_auth_cookies(response: Response) -> None:
    response.delete_cookie(ACCESS_COOKIE, httponly=True, samesite="lax", secure=COOKIE_SECURE)
    response.delete_cookie(
        REFRESH_COOKIE, path=REFRESH_COOKIE_PATH, httponly=True, samesite="strict", secure=COOKIE_SECURE
    )


def _sign_in(response: Response, user_id: int) -> CurrentStudent:
    access, refresh = auth_service.start_login(user_id)
    _set_auth_cookies(response, access, refresh)
    return auth_service.get_current_student(user_id)


@router.post("/register", status_code=201)
def register(request: RegisterRequest, response: Response) -> CurrentStudent:
    user_id = auth_service.register(request.student_id, request.name, request.email, request.password)
    return _sign_in(response, user_id)


@router.post("/login")
def login(request: LoginRequest, response: Response) -> CurrentStudent:
    user_id = auth_service.authenticate(request.email, request.password)
    if user_id is None:
        # Same message for an unknown email and a wrong password.
        raise AppError(401, "invalid_credentials", "Incorrect email or password.")
    return _sign_in(response, user_id)


@router.post("/refresh", status_code=204)
def refresh(refresh_token: Annotated[str | None, Cookie(alias=REFRESH_COOKIE)] = None) -> Response:
    try:
        if not refresh_token:
            raise AppError(401, "not_authenticated", "Please sign in again.")
        access, new_refresh = auth_service.refresh(refresh_token)
    except AppError:
        # Do not leave dead cookies behind for the browser to keep sending.
        failure = Response(
            status_code=401,
            content='{"error_code":"not_authenticated","message":"Please sign in again.","detail":null}',
            media_type="application/json",
        )
        _clear_auth_cookies(failure)
        return failure
    response = Response(status_code=204)
    _set_auth_cookies(response, access, new_refresh)
    return response


@router.post("/logout", status_code=204)
def logout(refresh_token: Annotated[str | None, Cookie(alias=REFRESH_COOKIE)] = None) -> Response:
    auth_service.logout(refresh_token)
    response = Response(status_code=204)
    _clear_auth_cookies(response)
    return response


@router.get("/me")
def me(student: SignedInStudent) -> CurrentStudent:
    return student
