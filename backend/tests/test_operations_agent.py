import json
from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.actions.registry import ACTIONS
from app.agent import agent
from app.agent.tool_registry import STUDENT_TOOLS, TOOL_FUNCTIONS, TOOL_SCHEMAS
from app.core import clock
from app.db.models import GrievanceTicket
from app.main import app
from fakes import completion as _completion
from fakes import tool_call as _tool_call
from helpers import ASHA, ASHA_PROFILE, add_operations_data, sign_up

READ_TOOLS = {
    "check_library_availability": {"query": "algorithms"},
    "get_canteen_menu": {"day": "Monday"},
    "get_bus_schedule": {"route": "A"},
    "get_lost_and_found": {"keyword": "umbrella"},
    "check_study_room_availability": {"day": "tomorrow"},
    "get_grievance_status": {},
    "get_counselling_slots": {},
    "get_placement_drives": {},
    "check_placement_eligibility": {"drive": "PD-002"},
}
OWN_DATA = {"get_grievance_status", "get_counselling_slots", "check_placement_eligibility"}
WRITE_ACTIONS = {
    "reserve_library_book", "book_study_room", "report_maintenance_issue", "submit_lost_item",
    "create_grievance_ticket", "book_counselling_appointment",
}


@pytest.fixture(autouse=True)
def _data(db, monkeypatch):
    add_operations_data(db)
    moment = datetime(2026, 10, 19, 10, 10)
    monkeypatch.setattr(clock, "now", lambda: moment)
    monkeypatch.setattr(clock, "today", lambda: moment.date())


def run(use_fakes, name, args):
    client = use_fakes(_completion(tool_calls=[_tool_call("c1", name, args)]), _completion(content="done"))
    seen = {}
    original = client._create

    def spy(**kwargs):
        seen["messages"] = kwargs["messages"]
        return original(**kwargs)

    client.chat.completions.create = spy
    response = agent.run_agent("question", [], ASHA_PROFILE)
    tool = next(m for m in seen["messages"] if m["role"] == "tool")
    return response, json.loads(tool["content"])


def schema(name):
    return next(s["function"] for s in TOOL_SCHEMAS if s["function"]["name"] == name)


def test_every_tool_and_action_is_registered():
    for name in READ_TOOLS:
        assert name in TOOL_FUNCTIONS and schema(name)["description"]
    assert WRITE_ACTIONS <= set(ACTIONS) and WRITE_ACTIONS.isdisjoint(TOOL_FUNCTIONS)
    for name in WRITE_ACTIONS:
        assert "NOT complete" in schema(name)["description"]


def test_tools_about_the_student_are_bound_to_the_login():
    assert OWN_DATA <= STUDENT_TOOLS
    assert not (set(READ_TOOLS) - OWN_DATA) & STUDENT_TOOLS
    for name in list(READ_TOOLS) + list(WRITE_ACTIONS):
        assert "student_id" not in schema(name)["parameters"]["properties"]


@pytest.mark.parametrize("name, args", READ_TOOLS.items())
def test_each_tool_runs_through_the_agent_with_a_summary(use_fakes, name, args):
    response, result = run(use_fakes, name, args)
    entry = response.toolActivity[0]
    assert entry.status == "done" and "error" not in result
    assert entry.label != name and entry.resultSummary not in ("Done", "")


def test_the_summaries_say_something_useful(use_fakes):
    got = {n: run(use_fakes, n, a)[0].toolActivity[0].resultSummary for n, a in READ_TOOLS.items()}
    assert got == {
        "check_library_availability": "Algorithms: available (+1 more)",
        "get_canteen_menu": "4 items on Monday",
        "get_bus_schedule": "1 routes, 1 running today",
        "get_lost_and_found": "1 matching items",
        "check_study_room_availability": "2 rooms with free slots on 2026-10-20",
        "get_grievance_status": "0 tickets",
        "get_counselling_slots": "2 free slots",
        "get_placement_drives": "3 upcoming drives",
        "check_placement_eligibility": "Not eligible",
    }


def test_a_forged_student_id_is_ignored_by_the_new_student_tools(use_fakes):
    for name in OWN_DATA:
        args = dict(READ_TOOLS[name])
        _, own = run(use_fakes, name, args)
        _, forged = run(use_fakes, name, {**args, "student_id": "1RV24IS219"})
        assert own == forged


def test_a_malformed_argument_is_reported_to_the_model(use_fakes):
    response, result = run(use_fakes, "get_lost_and_found", {"keyword": "x" * 100})
    assert response.toolActivity[0].status == "error" and "keyword" in result["error"]
    response, _ = run(use_fakes, "check_study_room_availability", {"min_capacity": 0})
    assert response.toolActivity[0].status == "error"


@pytest.fixture
def asha(db):
    return sign_up(TestClient(app))


def test_the_model_proposes_a_booking_and_only_the_student_makes_it_happen(asha, use_fakes, db):
    from app.db.models import RoomBooking

    use_fakes(_completion(tool_calls=[_tool_call("c1", "book_study_room", {"room_id": "DR-7", "date": "tomorrow", "time_slot": "14:00"})]))
    reply = asha.post("/api/chat", json={"message": "book DR-7 tomorrow at 2"}).json()
    assert reply["confirmation"]["title"] == "Book Discussion Room 7"
    with db() as session:
        assert session.scalars(select(RoomBooking)).all() == []
    assert asha.post(f"/api/actions/{reply['confirmation']['action_id']}/confirm").json()["success"] is True
    with db() as session:
        assert len(session.scalars(select(RoomBooking)).all()) == 1


def test_a_safety_concern_reaches_the_student_as_guidance_not_a_ticket(asha, use_fakes, db):
    use_fakes(_completion(tool_calls=[_tool_call("c1", "create_grievance_ticket", {"category": "hostel", "description": "Seniors in my block are ragging me every night and it is getting worse"})]))
    reply = asha.post("/api/chat", json={"message": "seniors are ragging me"}).json()
    assert reply["confirmation"] is None and "Anti-Ragging Committee" in reply["reply"]
    with db() as session:
        assert session.scalars(select(GrievanceTicket)).all() == []
