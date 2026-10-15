"""Every endpoint, called the way a real client does: over HTTP with httpx.AsyncClient.

The access table below must list every operation in the application's OpenAPI schema, so a new endpoint
cannot be added without saying who may use it. Each is then tried as everyone: signed out, and signed in
as each of the four roles."""
import asyncio
import json
from contextlib import asynccontextmanager
from uuid import uuid4

import httpx
import pytest
from httpx import ASGITransport

from app.main import app
from app.models.auth import NewStaffAccount
from app.services import auth_service
from helpers import ADMIN, ASHA, FACULTY, STAFF

pytestmark = pytest.mark.asyncio

ROLES = ("student", "faculty", "staff", "admin")
PUBLIC = "public"
ANY_SIGNED_IN = "any"
REFRESH_COOKIE = "refresh"  # needs the refresh cookie, not an access token

# (method, path) -> who may use it: PUBLIC, ANY_SIGNED_IN, or the roles allowed
ACCESS: dict[tuple[str, str], object] = {
    ("POST", "/api/actions/{action_id}/cancel"): {"student"},
    ("POST", "/api/actions/{action_id}/confirm"): {"student"},
    ("GET", "/api/admin/analytics"): {"admin"},
    ("POST", "/api/admin/events"): {"faculty", "admin"},
    ("PUT", "/api/admin/events/{event_id}"): {"faculty", "admin"},
    ("DELETE", "/api/admin/events/{event_id}"): {"faculty", "admin"},
    ("GET", "/api/admin/events/{event_id}/registrations"): {"faculty", "admin"},
    ("POST", "/api/admin/events/{event_id}/registrations/export"): {"faculty", "admin"},
    ("GET", "/api/admin/grievances"): {"staff", "admin"},
    ("PUT", "/api/admin/grievances/{ticket_id}"): {"staff", "admin"},
    ("POST", "/api/admin/knowledge/ingest"): {"admin"},
    ("GET", "/api/admin/knowledge/status"): {"admin"},
    ("POST", "/api/admin/knowledge/upload"): {"admin"},
    ("DELETE", "/api/admin/knowledge/{document_name}"): {"admin"},
    ("GET", "/api/admin/knowledge/{document_name}/chunks"): {"admin"},
    ("POST", "/api/admin/rag/eval"): {"admin"},
    ("GET", "/api/admin/rag/eval"): {"admin"},
    ("GET", "/api/admin/students"): {"admin"},
    ("POST", "/api/admin/students/import"): {"admin"},
    ("GET", "/api/admin/students/{student_id}"): {"admin"},
    ("POST", "/api/auth/login"): PUBLIC,
    ("POST", "/api/auth/logout"): PUBLIC,
    ("GET", "/api/auth/me"): ANY_SIGNED_IN,
    ("POST", "/api/auth/refresh"): REFRESH_COOKIE,
    ("POST", "/api/auth/register"): PUBLIC,
    ("POST", "/api/chat"): {"student"},
    ("GET", "/api/chat/history"): {"student"},
    ("GET", "/api/chat/sessions"): {"student"},
    ("DELETE", "/api/chat/sessions/{session_id}"): {"student"},
    ("GET", "/api/chat/sessions/{session_id}/summary"): {"student"},
    ("POST", "/api/chat/stream"): {"student"},
    ("GET", "/api/events"): PUBLIC,
    ("GET", "/api/events/{event_id}"): PUBLIC,
    ("GET", "/api/staff/registrations"): {"staff", "admin"},
    ("GET", "/api/staff/registrations/export"): {"staff", "admin"},
    ("GET", "/api/students/me/profile"): {"student"},
    ("PUT", "/api/students/me/profile"): {"student"},
    ("GET", "/health"): PUBLIC,
}


def operations() -> set[tuple[str, str]]:
    return {(method.upper(), path) for path, ops in app.openapi()["paths"].items() for method in ops}


def concrete(path: str) -> str:
    out = path
    for name in ("action_id", "session_id"):
        out = out.replace("{" + name + "}", str(uuid4()))
    import re

    return re.sub(r"\{[^}]+\}", "dummy", out)


def new_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@asynccontextmanager
async def session(role: str):
    """A client signed in as the role, closed afterwards."""
    client = await _signed_in(role)
    try:
        yield client
    finally:
        await client.aclose()


async def _signed_in(role: str) -> httpx.AsyncClient:
    client = new_client()
    if role == "student":
        response = await client.post("/api/auth/register", json=ASHA)
        assert response.status_code == 201, response.text
        return client
    account = {"student": ASHA, "faculty": FACULTY, "staff": STAFF, "admin": ADMIN}[role]
    auth_service.create_staff_account(NewStaffAccount(**account))
    response = await client.post("/api/auth/login", json={"email": account["email"], "password": account["password"]})
    assert response.status_code == 200, response.text
    return client


async def call(client: httpx.AsyncClient, method: str, path: str) -> int:
    response = await client.request(method, concrete(path), json={} if method in ("POST", "PUT") else None)
    return response.status_code


async def test_the_access_table_covers_every_operation_and_nothing_else():
    assert operations() == set(ACCESS), "an endpoint was added or removed without updating the access table"


async def test_signed_out_callers_get_a_401_everywhere_except_the_public_endpoints(db):
    async with new_client() as client:
        for (method, path), who in ACCESS.items():
            status = await call(client, method, path)
            if who == PUBLIC:
                assert status not in (401, 403), (method, path, status)
            elif who == REFRESH_COOKIE:
                assert status == 401, (method, path, status)
            else:
                assert status == 401, (method, path, status)


@pytest.mark.parametrize("role", ROLES)
async def test_each_role_can_use_what_it_may_and_is_refused_the_rest(db, role):
    async with session(role) as client:
        for (method, path), who in ACCESS.items():
            if path in ("/api/auth/logout", "/api/auth/refresh", "/api/auth/login", "/api/auth/register"):
                continue  # they end or replace the session being used
            status = await call(client, method, path)
            allowed = who in (PUBLIC, ANY_SIGNED_IN) or (isinstance(who, set) and role in who)
            if allowed:
                assert status not in (401, 403), (role, method, path, status)
            else:
                assert status == 403, (role, method, path, status)


async def test_a_denied_answer_has_the_standard_error_shape(db):
    async with new_client() as client:
        response = await client.get("/api/admin/analytics")
    assert response.status_code == 401
    assert set(response.json()) == {"error_code", "message", "detail"} and response.json()["error_code"] == "not_authenticated"


async def test_every_response_carries_a_request_id(db):
    async with new_client() as client:
        ids = {(await client.get("/api/events")).headers["x-request-id"] for _ in range(3)}
    assert len(ids) == 3


async def test_many_requests_at_once_are_all_answered(db):
    async with new_client() as client:
        responses = await asyncio.gather(*(client.get("/api/events") for _ in range(30)))
    assert [r.status_code for r in responses] == [200] * 30


async def test_a_chat_reply_streams_over_async_http(db, monkeypatch):
    from app.agent import agent
    from fakes import FakeGroq, fake_llm
    from fakes import completion as _completion

    client_llm = fake_llm(FakeGroq(_completion(content="Hello from the stream")))
    monkeypatch.setattr(agent, "get_llm_client", lambda: client_llm)
    monkeypatch.setattr(agent, "retrieve", lambda m: [])
    async with session("student") as client:
        events = []
        async with client.stream("POST", "/api/chat/stream", json={"message": "hi"}) as response:
            assert response.status_code == 200 and response.headers["content-type"].startswith("text/event-stream")
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    events.append(json.loads(line[6:]))
    assert events[-1]["type"] == "done" and events[-1]["payload"]["reply"] == "Hello from the stream"
    assert "".join(e["payload"]["text"] for e in events if e["type"] == "token") == "Hello from the stream"


async def test_a_real_workflow_over_async_http(db, monkeypatch):
    """Sign up, look at events, have the assistant propose a registration, approve it, see it on the admin roster."""
    from app.agent import agent
    from fakes import FakeGroq, fake_llm
    from fakes import completion as _completion
    from fakes import tool_call as _tool_call

    llm = fake_llm(FakeGroq(_completion(tool_calls=[_tool_call("c1", "register_for_event", {"event_id": "evt_ai_001"})])))
    monkeypatch.setattr(agent, "get_llm_client", lambda: llm)
    monkeypatch.setattr(agent, "retrieve", lambda m: [])

    async with session("student") as student, session("admin") as admin:
        events = (await student.get("/api/events")).json()
        assert [e["id"] for e in events] == ["evt_ai_001", "evt_web_002"]
        reply = (await student.post("/api/chat", json={"message": "register me for the AI workshop"})).json()
        action_id = reply["confirmation"]["action_id"]
        assert (await admin.get("/api/admin/events/evt_ai_001/registrations")).json()["registrations"] == []
        outcome = (await student.post(f"/api/actions/{action_id}/confirm")).json()
        assert outcome["success"] is True
        roster = (await admin.get("/api/admin/events/evt_ai_001/registrations")).json()
        assert [r["student_id"] for r in roster["registrations"]] == [ASHA["student_id"]]
        assert (await student.get("/api/events/evt_ai_001")).json()["registered"] == 5


async def test_two_simultaneous_confirmations_register_once(db, monkeypatch):
    from app.agent import agent
    from fakes import FakeGroq, fake_llm
    from fakes import completion as _completion
    from fakes import tool_call as _tool_call

    llm = fake_llm(FakeGroq(_completion(tool_calls=[_tool_call("c1", "register_for_event", {"event_id": "evt_ai_001"})])))
    monkeypatch.setattr(agent, "get_llm_client", lambda: llm)
    monkeypatch.setattr(agent, "retrieve", lambda m: [])
    async with session("student") as student:
        action_id = (await student.post("/api/chat", json={"message": "register me"})).json()["confirmation"]["action_id"]
        first, second = await asyncio.gather(
            student.post(f"/api/actions/{action_id}/confirm"), student.post(f"/api/actions/{action_id}/confirm")
        )
        assert sorted([first.status_code, second.status_code]) in ([200, 200], [200, 409])
        assert (await student.get("/api/events/evt_ai_001")).json()["registered"] == 5
