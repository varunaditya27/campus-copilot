import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, update

from app.actions.base import ActionError
from app.actions.registry import ACTION_SCHEMAS, ACTIONS
from app.actions import registration
from app.agent import agent
from app.agent.tool_registry import TOOL_FUNCTIONS, TOOL_SCHEMAS
from app.core.errors import AppError
from app.db.models import Event, PendingAction, Registration
from app.main import app
from app.services import action_service
from fakes import completion as _completion
from fakes import tool_call as _tool_call
from helpers import ADMIN, ASHA, ASHA_PROFILE, FACULTY, RAVI, RAVI_PROFILE, all_registrations, sign_in_as, sign_up



def pending(db):
    with db() as session:
        return list(session.scalars(select(PendingAction).order_by(PendingAction.created_at)))


def propose(student=ASHA_PROFILE, event_id="evt_ai_001"):
    return action_service.propose(student, "register_for_event", {"event_id": event_id})


# --- the registration action: preparing it


def test_a_valid_request_becomes_a_preview(db):
    prepared = registration.prepare({"event_id": "evt_ai_001"}, ASHA_PROFILE)
    assert prepared.title == "Register for AI Workshop" and prepared.params == {"event_id": "evt_ai_001"}
    assert {line.label: line.value for line in prepared.lines} == {
        "Event": "AI Workshop", "When": "2026-09-01 at 10:00", "Where": "Hall A", "Student": "1RV23IS101",
    }


@pytest.mark.parametrize("args", [{}, {"event_id": "nope"}, {"event_id": 7}, {"event_id": None}, {"event_id": ["evt_ai_001"]}])
def test_an_unknown_or_malformed_event_is_refused_in_plain_words(db, args):
    with pytest.raises(ActionError, match="couldn't find that event"):
        registration.prepare(args, ASHA_PROFILE)


def test_a_full_event_is_refused_before_any_confirmation(db):
    with pytest.raises(ActionError, match="Web Night is full"):
        registration.prepare({"event_id": "evt_web_002"}, ASHA_PROFILE)


def test_an_event_the_student_is_already_in_is_refused(db):
    action_service.confirm(UUID(propose().action_id), ASHA_PROFILE)
    with pytest.raises(ActionError, match="already registered for AI Workshop"):
        registration.prepare({"event_id": "evt_ai_001"}, ASHA_PROFILE)


def test_the_action_is_listed_for_the_model_without_a_student_id():
    schema = ACTIONS["register_for_event"].schema
    assert schema in ACTION_SCHEMAS and schema in TOOL_SCHEMAS
    assert list(schema["function"]["parameters"]["properties"]) == ["event_id"]


def test_actions_are_not_tools_the_model_can_run():
    assert not set(ACTIONS) & set(TOOL_FUNCTIONS)


# --- proposing


def test_a_proposal_is_stored_on_the_server_with_an_expiry(db):
    confirmation = propose()

    (row,) = pending(db)
    assert str(row.id) == confirmation.action_id and row.status == "pending"
    assert (row.student_id, row.action, row.params) == ("1RV23IS101", "register_for_event", {"event_id": "evt_ai_001"})
    ten_minutes = timedelta(minutes=action_service.CONFIRMATION_MINUTES)
    assert abs(confirmation.expires_at - (datetime.now(timezone.utc) + ten_minutes)) < timedelta(seconds=5)
    assert all_registrations(db) == []


def test_only_the_checked_parameters_are_stored(db):
    action_service.propose(ASHA_PROFILE, "register_for_event", {"event_id": "evt_ai_001", "student_id": "1RV24IS219", "extra": 1})
    assert pending(db)[0].params == {"event_id": "evt_ai_001"}


def test_a_refused_proposal_stores_nothing(db):
    with pytest.raises(ActionError):
        propose(event_id="nope")
    assert pending(db) == []


# --- confirming


def test_confirming_runs_the_stored_action(db):
    confirmation = propose()

    outcome = action_service.confirm(UUID(confirmation.action_id), ASHA_PROFILE)

    assert (outcome.status, outcome.success, outcome.message) == ("confirmed", True, "You're registered for AI Workshop.")
    assert outcome.details == {"Registration ID": "REG-00001"}
    assert [r.student_id for r in all_registrations(db)] == ["1RV23IS101"]
    assert pending(db)[0].status == "confirmed" and pending(db)[0].resolved_at is not None


def test_confirming_twice_runs_it_once_and_gives_the_same_answer(db):
    action_id = UUID(propose().action_id)
    first = action_service.confirm(action_id, ASHA_PROFILE)
    second = action_service.confirm(action_id, ASHA_PROFILE)
    assert first == second and len(all_registrations(db)) == 1


def test_simultaneous_confirmations_run_the_action_exactly_once(db):
    action_id = UUID(propose().action_id)
    barrier = threading.Barrier(6)

    def go(_):
        barrier.wait()
        try:
            return action_service.confirm(action_id, ASHA_PROFILE)
        except AppError as exc:
            return exc.error_code

    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(go, range(6)))

    assert len(all_registrations(db)) == 1
    outcomes = [r for r in results if not isinstance(r, str)]
    assert outcomes and all(o.success for o in outcomes)
    assert all(r == "action_in_progress" for r in results if isinstance(r, str))


def test_someone_elses_action_cannot_be_confirmed_and_looks_unknown(db):
    action_id = UUID(propose().action_id)
    with pytest.raises(AppError) as info:
        action_service.confirm(action_id, RAVI_PROFILE)
    assert info.value.status_code == 404 and all_registrations(db) == []
    assert pending(db)[0].status == "pending"


def test_an_unknown_action_is_not_found(db):
    with pytest.raises(AppError) as info:
        action_service.confirm(uuid4(), ASHA_PROFILE)
    assert info.value.status_code == 404


def test_an_expired_action_cannot_be_confirmed(db):
    action_id = UUID(propose().action_id)
    with db.begin() as session:
        session.execute(update(PendingAction).values(expires_at=datetime.now(timezone.utc) - timedelta(seconds=1)))

    with pytest.raises(AppError) as info:
        action_service.confirm(action_id, ASHA_PROFILE)

    assert (info.value.status_code, info.value.error_code) == (410, "action_expired")
    assert all_registrations(db) == [] and pending(db)[0].status == "expired"


def test_if_the_event_fills_up_while_waiting_nothing_is_done(db):
    action_id = UUID(propose().action_id)
    with db.begin() as session:
        session.execute(update(Event).where(Event.id == "evt_ai_001").values(registered=10))

    outcome = action_service.confirm(action_id, ASHA_PROFILE)

    assert (outcome.status, outcome.success, outcome.message) == ("failed", False, "This event is full")
    assert all_registrations(db) == []
    with pytest.raises(AppError) as info:
        action_service.confirm(action_id, ASHA_PROFILE)
    assert info.value.error_code == "action_failed"


def test_an_unexpected_error_while_running_is_reported_without_details(db, monkeypatch):
    action_id = UUID(propose().action_id)

    def explode(params, student):
        raise RuntimeError("secret detail")

    monkeypatch.setitem(ACTIONS, "register_for_event", replace(ACTIONS["register_for_event"], execute=explode))

    outcome = action_service.confirm(action_id, ASHA_PROFILE)

    assert outcome.success is False and "secret detail" not in outcome.message
    assert pending(db)[0].status == "failed"


# --- cancelling


def test_a_cancelled_action_can_no_longer_be_confirmed(db):
    action_id = UUID(propose().action_id)
    outcome = action_service.cancel(action_id, ASHA_PROFILE)
    assert (outcome.status, outcome.success) == ("cancelled", False)
    with pytest.raises(AppError) as info:
        action_service.confirm(action_id, ASHA_PROFILE)
    assert (info.value.status_code, info.value.error_code) == (409, "action_cancelled")
    assert all_registrations(db) == []


def test_cancelling_twice_is_fine(db):
    action_id = UUID(propose().action_id)
    assert action_service.cancel(action_id, ASHA_PROFILE) == action_service.cancel(action_id, ASHA_PROFILE)


def test_an_action_that_already_ran_cannot_be_cancelled(db):
    action_id = UUID(propose().action_id)
    action_service.confirm(action_id, ASHA_PROFILE)
    with pytest.raises(AppError) as info:
        action_service.cancel(action_id, ASHA_PROFILE)
    assert info.value.error_code == "action_confirmed" and len(all_registrations(db)) == 1


def test_someone_elses_action_cannot_be_cancelled(db):
    action_id = UUID(propose().action_id)
    with pytest.raises(AppError) as info:
        action_service.cancel(action_id, RAVI_PROFILE)
    assert info.value.status_code == 404 and pending(db)[0].status == "pending"


# --- over HTTP


@pytest.fixture
def asha(db):
    return sign_up(TestClient(app), ASHA)


def test_the_endpoints_need_a_signed_in_student(db):
    action_id = uuid4()
    assert TestClient(app).post(f"/api/actions/{action_id}/confirm").status_code == 401
    assert TestClient(app).post(f"/api/actions/{action_id}/cancel").status_code == 401
    for account in (FACULTY, ADMIN):
        client = sign_in_as(account)
        assert client.post(f"/api/actions/{action_id}/confirm").status_code == 403


def test_confirming_over_http(asha, db):
    action_id = propose().action_id
    body = asha.post(f"/api/actions/{action_id}/confirm").json()
    assert body["success"] is True and body["details"] == {"Registration ID": "REG-00001"} and body["status"] == "confirmed"


def test_a_body_sent_with_the_confirmation_changes_nothing(asha, db):
    action_id = propose().action_id
    asha.post(f"/api/actions/{action_id}/confirm", json={"event_id": "evt_web_002", "student_id": "1RV24IS219"})
    assert [(r.student_id, r.event_id) for r in all_registrations(db)] == [("1RV23IS101", "evt_ai_001")]


def test_a_malformed_action_id_is_a_validation_error(asha):
    response = asha.post("/api/actions/not-a-uuid/confirm")
    assert (response.status_code, response.json()["error_code"]) == (422, "validation_error")


def test_a_confirmation_from_an_unknown_site_is_refused(asha, db):
    action_id = propose().action_id
    response = asha.post(f"/api/actions/{action_id}/confirm", headers={"Origin": "https://evil.example"})
    assert response.status_code == 403 and all_registrations(db) == []
    assert pending(db)[0].status == "pending"


def test_another_student_cannot_confirm_over_http(asha, db):
    action_id = propose().action_id
    ravi = sign_up(TestClient(app), RAVI)
    assert ravi.post(f"/api/actions/{action_id}/confirm").status_code == 404
    assert all_registrations(db) == []


def test_cancelling_over_http(asha, db):
    action_id = propose().action_id
    body = asha.post(f"/api/actions/{action_id}/cancel").json()
    assert (body["status"], body["success"], body["message"]) == ("cancelled", False, "Cancelled. Nothing was done.")


# --- the whole path, from the model's request to the approval


def test_the_model_proposes_and_only_the_student_can_make_it_happen(asha, db, use_fakes):
    use_fakes(_completion(tool_calls=[_tool_call("c1", "register_for_event", {"event_id": "evt_ai_001"})]))

    reply = asha.post("/api/chat", json={"message": "register me for the AI workshop"}).json()

    assert reply["confirmation"]["title"] == "Register for AI Workshop"
    assert all_registrations(db) == [], "proposing must not register anyone"
    action_id = reply["confirmation"]["action_id"]
    assert asha.post(f"/api/actions/{action_id}/confirm").json()["success"] is True
    assert len(all_registrations(db)) == 1


def test_a_model_that_keeps_asking_creates_proposals_but_never_registrations(asha, db, use_fakes):
    use_fakes(_completion(tool_calls=[_tool_call("c1", "register_for_event", {"event_id": "evt_ai_001"})]))
    for _ in range(3):
        asha.post("/api/chat", json={"message": "register me"})
    assert len(pending(db)) == 3 and all_registrations(db) == []


def test_the_model_cannot_reach_the_confirmation_through_a_tool(db, use_fakes):
    use_fakes(
        _completion(tool_calls=[_tool_call("c1", "confirm_action", {"action_id": str(uuid4())})]),
        _completion(content="done"),
    )
    response = agent.run_agent("confirm it", [], ASHA_PROFILE)
    assert response.toolActivity[0].status == "error" and response.confirmation is None
