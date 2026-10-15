from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, update

from app.core import security
from app.db.models import RefreshToken, User
from app.main import app
from app.services import auth_service
from helpers import ASHA, RAVI, sign_up


@pytest.fixture
def client(db):
    return TestClient(app)


def _cookie_header(response, name):
    return next(h for h in response.headers.get_list("set-cookie") if h.startswith(f"{name}="))


def _refresh_rows(db):
    with db() as session:
        return list(session.scalars(select(RefreshToken).order_by(RefreshToken.id)))


# --- registration


def test_register_creates_an_account_and_signs_in(db, client):
    response = client.post("/api/auth/register", json=ASHA)

    assert response.status_code == 201
    assert response.json() == {
        "user_id": 1, "student_id": "1RV23IS101", "name": "Asha",
        "program": "ISE", "year": 3, "email": "asha@example.com",
    }
    assert client.get("/api/auth/me").json()["student_id"] == "1RV23IS101"


def test_register_cookies_are_httponly_and_scoped(client):
    response = client.post("/api/auth/register", json=ASHA)

    access = _cookie_header(response, "access_token").lower()
    refresh = _cookie_header(response, "refresh_token").lower()
    assert "httponly" in access and "samesite=lax" in access and "max-age=900" in access
    assert "httponly" in refresh and "samesite=strict" in refresh and "path=/api/auth" in refresh


def test_password_is_stored_hashed(db, client):
    sign_up(client)
    with db() as session:
        stored = session.scalar(select(User.password_hash))
    assert stored.startswith("$argon2id$") and ASHA["password"] not in stored


def test_register_normalises_email_case(db, client):
    client.post("/api/auth/register", json={**ASHA, "email": "Asha@Example.COM"})
    with db() as session:
        assert session.scalar(select(User.email)) == "asha@example.com"


def test_name_match_ignores_case_and_spacing(client):
    response = client.post("/api/auth/register", json={**ASHA, "name": "  ASHA "})
    assert response.status_code == 201


@pytest.mark.parametrize(
    "overrides",
    [{"student_id": "1RV99ZZ999"}, {"name": "Someone Else"}],
    ids=["unknown-usn", "wrong-name"],
)
def test_register_must_match_the_roster(client, overrides):
    response = client.post("/api/auth/register", json={**ASHA, **overrides})
    assert response.status_code == 400
    assert response.json()["error_code"] == "student_not_matched"


def test_the_two_roster_failures_look_identical(client):
    unknown = client.post("/api/auth/register", json={**ASHA, "student_id": "1RV99ZZ999"}).json()
    wrong_name = client.post("/api/auth/register", json={**ASHA, "name": "Nope"}).json()
    assert unknown == wrong_name


def test_a_student_cannot_register_twice(client):
    sign_up(client)
    response = client.post("/api/auth/register", json={**ASHA, "email": "other@example.com"})
    assert (response.status_code, response.json()["error_code"]) == (409, "account_exists")


def test_an_email_cannot_be_reused(client):
    sign_up(client)
    response = client.post("/api/auth/register", json={**RAVI, "email": "ASHA@example.com"})
    assert (response.status_code, response.json()["error_code"]) == (409, "email_taken")


@pytest.mark.parametrize(
    "overrides",
    [{"password": "short"}, {"password": "x" * 129}, {"email": "not-an-email"}, {"student_id": "bad id"}, {"name": ""}],
    ids=["short-password", "huge-password", "bad-email", "bad-usn", "empty-name"],
)
def test_register_validates_input(client, overrides):
    response = client.post("/api/auth/register", json={**ASHA, **overrides})
    assert (response.status_code, response.json()["error_code"]) == (422, "validation_error")


# --- login


def test_login_with_the_right_password(client):
    sign_up(client)
    other_browser = TestClient(app)

    response = other_browser.post("/api/auth/login", json={"email": "ASHA@example.com", "password": ASHA["password"]})

    assert response.status_code == 200
    assert other_browser.get("/api/auth/me").json()["name"] == "Asha"


def test_wrong_password_and_unknown_email_get_the_same_answer(client):
    sign_up(client)
    wrong = TestClient(app).post("/api/auth/login", json={"email": ASHA["email"], "password": "not the password"})
    unknown = TestClient(app).post("/api/auth/login", json={"email": "nobody@example.com", "password": "not the password"})

    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()
    assert wrong.json()["error_code"] == "invalid_credentials"
    assert "set-cookie" not in wrong.headers


def test_an_inactive_account_cannot_sign_in(db, client):
    sign_up(client)
    with db.begin() as session:
        session.execute(update(User).values(is_active=False))

    response = TestClient(app).post("/api/auth/login", json={"email": ASHA["email"], "password": ASHA["password"]})
    assert response.status_code == 401
    assert client.get("/api/auth/me").status_code == 401


# --- identifying the caller


def test_me_needs_a_signed_in_user(client):
    response = client.get("/api/auth/me")
    assert (response.status_code, response.json()["error_code"]) == (401, "not_authenticated")


def test_a_forged_cookie_is_rejected(client):
    client.cookies.set("access_token", "x.y.z")
    assert client.get("/api/auth/me").status_code == 401


def test_an_expired_access_token_is_rejected(client):
    sign_up(client)
    past = datetime.now(timezone.utc) - timedelta(minutes=1)
    import jwt

    from app.core.config import JWT_SECRET

    client.cookies.set(
        "access_token",
        jwt.encode({"sub": "1", "typ": "access", "iat": past, "exp": past}, JWT_SECRET, algorithm="HS256"),
    )
    assert client.get("/api/auth/me").status_code == 401


def test_a_token_for_a_deleted_user_is_rejected(client):
    client.cookies.set("access_token", security.create_access_token(999))
    assert client.get("/api/auth/me").status_code == 401


# --- refresh


def test_refresh_issues_new_tokens_and_retires_the_old_one(db, client):
    sign_up(client)
    old_refresh = client.cookies.get("refresh_token", path="/api/auth")

    response = client.post("/api/auth/refresh")

    assert response.status_code == 204
    assert client.cookies.get("refresh_token", path="/api/auth") != old_refresh
    assert client.get("/api/auth/me").status_code == 200
    rows = _refresh_rows(db)
    assert len(rows) == 2 and rows[0].revoked_at is not None and rows[1].revoked_at is None
    assert rows[0].family_id == rows[1].family_id


def test_refresh_without_a_cookie_is_401(client):
    assert client.post("/api/auth/refresh").status_code == 401


def test_refresh_token_is_stored_only_as_a_hash(db, client):
    sign_up(client)
    raw = client.cookies.get("refresh_token", path="/api/auth")
    assert all(raw not in row.token_hash for row in _refresh_rows(db))
    assert _refresh_rows(db)[0].token_hash == security.hash_refresh_token(raw)


def test_reusing_an_old_refresh_token_revokes_the_whole_login(db, client):
    sign_up(client)
    stolen = client.cookies.get("refresh_token", path="/api/auth")
    client.post("/api/auth/refresh")  # the real user rotates the token
    with db.begin() as session:  # ...a while ago, so this is not a simultaneous refresh
        session.execute(update(RefreshToken).where(RefreshToken.revoked_at.is_not(None)).values(
            revoked_at=datetime.now(timezone.utc) - timedelta(minutes=5)))

    attacker = TestClient(app)
    attacker.cookies.set("refresh_token", stolen, path="/api/auth")
    assert attacker.post("/api/auth/refresh").status_code == 401

    assert all(row.revoked_at is not None for row in _refresh_rows(db))
    assert client.post("/api/auth/refresh").status_code == 401  # the real user must sign in again


def test_two_tabs_refreshing_at_once_do_not_end_the_login(db, client):
    sign_up(client)
    first_token = client.cookies.get("refresh_token", path="/api/auth")
    client.post("/api/auth/refresh")

    second_tab = TestClient(app)
    second_tab.cookies.set("refresh_token", first_token, path="/api/auth")
    assert second_tab.post("/api/auth/refresh").status_code == 401

    assert client.post("/api/auth/refresh").status_code == 204  # still signed in


def test_an_expired_refresh_token_is_rejected(db, client):
    sign_up(client)
    with db.begin() as session:
        session.execute(update(RefreshToken).values(expires_at=datetime.now(timezone.utc) - timedelta(seconds=1)))
    assert client.post("/api/auth/refresh").status_code == 401


def test_a_failed_refresh_clears_the_cookies(client):
    client.cookies.set("refresh_token", "bogus", path="/api/auth")
    response = client.post("/api/auth/refresh")
    cookies = " ".join(response.headers.get_list("set-cookie"))
    assert response.status_code == 401
    assert "refresh_token=" in cookies and "max-age=0" in cookies.lower()


def test_only_one_of_two_simultaneous_refreshes_can_win(db, client):
    sign_up(client)
    raw = client.cookies.get("refresh_token", path="/api/auth")
    outcomes = []
    for _ in range(2):
        try:
            outcomes.append(auth_service.refresh(raw))
        except Exception as exc:
            outcomes.append(exc)
    assert sum(isinstance(o, tuple) for o in outcomes) == 1


# --- logout


def test_logout_revokes_the_login_on_the_server(db, client):
    sign_up(client)
    refresh_token = client.cookies.get("refresh_token", path="/api/auth")

    response = client.post("/api/auth/logout")

    assert response.status_code == 204
    assert client.get("/api/auth/me").status_code == 401
    assert all(row.revoked_at is not None for row in _refresh_rows(db))
    replay = TestClient(app)
    replay.cookies.set("refresh_token", refresh_token, path="/api/auth")
    assert replay.post("/api/auth/refresh").status_code == 401


def test_logout_is_safe_to_repeat_and_when_signed_out(client):
    assert client.post("/api/auth/logout").status_code == 204
    sign_up(client)
    assert client.post("/api/auth/logout").status_code == 204
    assert client.post("/api/auth/logout").status_code == 204


def test_logging_out_one_browser_leaves_the_others_signed_in(db, client):
    sign_up(client)
    other = TestClient(app)
    other.post("/api/auth/login", json={"email": ASHA["email"], "password": ASHA["password"]})

    client.post("/api/auth/logout")

    assert other.post("/api/auth/refresh").status_code == 204


# --- CSRF defence


def test_a_post_from_an_unknown_origin_is_refused(client):
    sign_up(client)
    response = client.post("/api/auth/logout", headers={"Origin": "https://evil.example"})
    assert (response.status_code, response.json()["error_code"]) == (403, "forbidden_origin")
    assert client.get("/api/auth/me").status_code == 200  # nothing happened


def test_the_null_origin_is_refused(client):
    assert client.post("/api/auth/logout", headers={"Origin": "null"}).status_code == 403


def test_a_post_from_our_own_origin_is_allowed(client):
    from app.core.config import CORS_ORIGINS

    sign_up(client)
    assert client.post("/api/auth/logout", headers={"Origin": CORS_ORIGINS[0]}).status_code == 204


def test_requests_without_an_origin_header_are_allowed(client):
    assert client.post("/api/auth/logout").status_code == 204


def test_reads_are_not_origin_checked(client):
    assert client.get("/api/events", headers={"Origin": "https://evil.example"}).status_code == 200


def test_cors_headers_are_only_granted_to_allowed_origins(client):
    from app.core.config import CORS_ORIGINS

    response = client.post("/api/auth/logout", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in response.headers  # not an allowed origin
    ok = client.get("/api/events", headers={"Origin": CORS_ORIGINS[0]})
    assert ok.headers["access-control-allow-origin"] == CORS_ORIGINS[0]
