import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from uuid import UUID

import pytest
from sqlalchemy import select, update

from app.actions.base import ActionError
from app.core import clock
from app.db.models import Event, EventDetail, EventFeedback, EventWaitlist, Registration, Student
from app.services import action_service, engagement_service as svc
from helpers import ASHA_PROFILE, RAVI_PROFILE, register_through_approval

ASHA = "1RV23IS101"
RAVI = "1RV24IS219"
ARJUN = "1RV22CS220"
ARJUN_PROFILE = RAVI_PROFILE.model_copy(update={"user_id": 3, "student_id": ARJUN, "name": "Arjun"})
BEFORE = datetime(2026, 8, 20, 9, 0)  # the test events are on 2026-09-01 at 10:00
AFTER = datetime(2026, 9, 2, 9, 0)


@pytest.fixture
def set_now(monkeypatch):
    def setter(moment):
        monkeypatch.setattr(clock, "now", lambda: moment)
        monkeypatch.setattr(clock, "today", lambda: moment.date())

    setter(BEFORE)
    return setter


@pytest.fixture(autouse=True)
def arjun(db):
    with db.begin() as session:
        session.add(Student(student_id=ARJUN, name="Arjun", program="CSE", year=4))


def act(student, name, **args):
    confirmation = action_service.propose(student, name, args)
    return action_service.confirm(UUID(confirmation.action_id), student)


def refused(student, name, **args):
    with pytest.raises(ActionError) as info:
        action_service.propose(student, name, args)
    return str(info.value)


def seats(db, event_id="evt_ai_001"):
    with db() as session:
        return session.scalar(select(Event.registered).where(Event.id == event_id))


def fill(db, event_id="evt_ai_001"):
    with db.begin() as session:
        session.execute(update(Event).where(Event.id == event_id).values(registered=Event.capacity - 1))


# --- detail and my registrations


def test_event_detail_has_everything_and_the_students_status(db, set_now):
    with db.begin() as session:
        session.add(EventDetail(event_id="evt_ai_001", prerequisites="Basic Python", materials="Laptop"))
    detail = svc.event_detail(ASHA, "evt_ai_001")
    assert (detail["name"], detail["organizer"], detail["venue"], detail["seats_left"]) == ("AI Workshop", "Test Club", "Hall A", 6)
    assert (detail["prerequisites"], detail["materials_needed"], detail["timing"], detail["your_status"]) == ("Basic Python", "Laptop", "upcoming", "not registered")


def test_an_event_without_extra_details_still_answers(db, set_now):
    detail = svc.event_detail(ASHA, "evt_ai_001")
    assert detail["prerequisites"] is None and detail["materials_needed"] is None


def test_the_students_own_status_is_shown(db, set_now):
    register_through_approval(ASHA_PROFILE)
    detail = svc.event_detail(ASHA, "evt_ai_001")
    assert (detail["your_status"], detail["your_registration_id"]) == ("registered", "REG-00001")
    assert svc.event_detail(RAVI, "evt_ai_001")["your_status"] == "not registered"


def test_an_event_that_has_started_is_marked_past(db, set_now):
    set_now(AFTER)
    assert svc.event_detail(ASHA, "evt_ai_001")["timing"] == "past"


def test_an_unknown_event_is_an_error(db, set_now):
    assert "No event found" in svc.event_detail(ASHA, "nope")["error"]


def test_my_registrations_lists_events_with_their_timing(db, set_now):
    assert svc.my_registrations(ASHA)["message"] == "You are not registered for any events."
    register_through_approval(ASHA_PROFILE)
    result = svc.my_registrations(ASHA)
    assert result["registrations"] == [
        {"registration_id": "REG-00001", "event_id": "evt_ai_001", "name": "AI Workshop", "date": "2026-09-01", "time": "10:00", "venue": "Hall A", "timing": "upcoming"}
    ]
    assert svc.my_registrations(RAVI)["registrations"] == []


# --- cancelling


def test_cancelling_releases_the_seat_and_allows_registering_again(db, set_now):
    register_through_approval(ASHA_PROFILE)
    assert seats(db) == 5
    outcome = act(ASHA_PROFILE, "cancel_event_registration", event_id="evt_ai_001")
    assert outcome.success and seats(db) == 4
    with db() as session:
        assert session.scalars(select(Registration)).all() == []
    assert register_through_approval(ASHA_PROFILE).success


@pytest.mark.parametrize("event, reason", [("evt_web_002", "not registered"), ("nope", "couldn't find")])
def test_only_your_own_registration_can_be_cancelled(db, set_now, event, reason):
    assert reason in refused(ASHA_PROFILE, "cancel_event_registration", event_id=event)


def test_someone_elses_registration_cannot_be_cancelled(db, set_now):
    register_through_approval(ASHA_PROFILE)
    assert "not registered" in refused(RAVI_PROFILE, "cancel_event_registration", event_id="evt_ai_001")
    assert seats(db) == 5


def test_an_event_that_has_started_cannot_be_left(db, set_now):
    register_through_approval(ASHA_PROFILE)
    set_now(AFTER)
    assert "already started" in refused(ASHA_PROFILE, "cancel_event_registration", event_id="evt_ai_001")


def test_the_first_person_waiting_gets_the_freed_seat(db, set_now):
    fill(db)
    register_through_approval(ASHA_PROFILE)  # the last seat
    act(RAVI_PROFILE, "join_event_waitlist", event_id="evt_ai_001")
    act(ARJUN_PROFILE, "join_event_waitlist", event_id="evt_ai_001")

    assert act(ASHA_PROFILE, "cancel_event_registration", event_id="evt_ai_001").success

    with db() as session:
        holders = [r.student_id for r in session.scalars(select(Registration))]
        waiting = [w.student_id for w in session.scalars(select(EventWaitlist))]
    assert holders == [RAVI] and waiting == [ARJUN] and seats(db) == 10
    assert svc.event_detail(ARJUN, "evt_ai_001")["your_waitlist_position"] == 1
    assert svc.event_detail(RAVI, "evt_ai_001")["your_registration_id"].startswith("REG-")


def test_the_preview_warns_that_the_seat_goes_to_the_waitlist(db, set_now):
    fill(db)
    register_through_approval(ASHA_PROFILE)
    act(RAVI_PROFILE, "join_event_waitlist", event_id="evt_ai_001")
    lines = {l.label: l.value for l in action_service.propose(ASHA_PROFILE, "cancel_event_registration", {"event_id": "evt_ai_001"}).lines}
    assert "first of 1 students" in lines["Note"]


def test_cancelling_twice_at_once_frees_one_seat_only(db, set_now):
    register_through_approval(ASHA_PROFILE)
    first = action_service.propose(ASHA_PROFILE, "cancel_event_registration", {"event_id": "evt_ai_001"})
    second = action_service.propose(ASHA_PROFILE, "cancel_event_registration", {"event_id": "evt_ai_001"})
    barrier = threading.Barrier(2)

    def go(confirmation):
        barrier.wait()
        return action_service.confirm(UUID(confirmation.action_id), ASHA_PROFILE)

    with ThreadPoolExecutor(2) as pool:
        outcomes = list(pool.map(go, [first, second]))
    assert sorted(o.success for o in outcomes) == [False, True] and seats(db) == 4


# --- waitlist


def test_joining_a_full_events_waitlist_gives_a_place(db, set_now):
    outcome = act(RAVI_PROFILE, "join_event_waitlist", event_id="evt_web_002")
    assert outcome.details == {"Waitlist place": "1"}
    assert act(ARJUN_PROFILE, "join_event_waitlist", event_id="evt_web_002").details == {"Waitlist place": "2"}
    assert svc.my_registrations(RAVI)["waitlisted"] == [{"event_id": "evt_web_002", "name": "Web Night", "date": "2026-09-01", "position": 1}]


@pytest.mark.parametrize(
    "event, reason", [("evt_ai_001", "still has seats"), ("nope", "couldn't find")]
)
def test_the_waitlist_is_only_for_full_events_that_exist(db, set_now, event, reason):
    assert reason in refused(RAVI_PROFILE, "join_event_waitlist", event_id=event)


def test_a_registered_or_waiting_student_cannot_join_again(db, set_now):
    fill(db)
    register_through_approval(ASHA_PROFILE)
    assert "already registered" in refused(ASHA_PROFILE, "join_event_waitlist", event_id="evt_ai_001")
    act(RAVI_PROFILE, "join_event_waitlist", event_id="evt_ai_001")
    assert "already on the waitlist" in refused(RAVI_PROFILE, "join_event_waitlist", event_id="evt_ai_001")


def test_an_event_that_has_started_has_no_waitlist(db, set_now):
    set_now(AFTER)
    assert "already started" in refused(RAVI_PROFILE, "join_event_waitlist", event_id="evt_web_002")


def test_if_a_seat_opens_while_deciding_the_student_is_told_to_register(db, set_now):
    confirmation = action_service.propose(RAVI_PROFILE, "join_event_waitlist", {"event_id": "evt_web_002"})
    with db.begin() as session:
        session.execute(update(Event).where(Event.id == "evt_web_002").values(registered=4))
    outcome = action_service.confirm(UUID(confirmation.action_id), RAVI_PROFILE)
    assert outcome.success is False and "register for it directly" in outcome.message


def test_the_register_refusal_points_to_the_waitlist(db, set_now):
    assert "waitlist" in refused(RAVI_PROFILE, "register_for_event", event_id="evt_web_002")


# --- feedback


def test_the_form_describes_its_fields(db, set_now):
    register_through_approval(ASHA_PROFILE)
    set_now(AFTER)
    form = svc.feedback_form(ASHA, "evt_ai_001")
    assert form["can_submit"] is True and form["reason"] is None
    assert [f["name"] for f in form["fields"]] == ["rating", "comments"]
    assert form["fields"][0] == {"name": "rating", "type": "integer", "required": True, "min": 1, "max": 5, "meaning": "1 is poor, 5 is excellent"}


@pytest.mark.parametrize("registered, now, reason", [(False, AFTER, "registered for"), (True, BEFORE, "hasn't happened yet")])
def test_the_form_says_why_feedback_is_not_open(db, set_now, registered, now, reason):
    if registered:
        register_through_approval(ASHA_PROFILE)
    set_now(now)
    form = svc.feedback_form(ASHA, "evt_ai_001")
    assert form["can_submit"] is False and reason in form["reason"]


def test_feedback_is_stored_and_only_once(db, set_now):
    register_through_approval(ASHA_PROFILE)
    set_now(AFTER)
    assert act(ASHA_PROFILE, "submit_event_feedback", event_id="evt_ai_001", rating=4, comments="  Great session  ").success
    with db() as session:
        row = session.scalar(select(EventFeedback))
        assert (row.student_id, row.rating, row.comments) == (ASHA, 4, "Great session")
    assert "already given feedback" in refused(ASHA_PROFILE, "submit_event_feedback", event_id="evt_ai_001", rating=5)
    assert svc.feedback_form(ASHA, "evt_ai_001")["can_submit"] is False


def test_comments_are_optional_and_blank_ones_are_dropped(db, set_now):
    register_through_approval(ASHA_PROFILE)
    set_now(AFTER)
    act(ASHA_PROFILE, "submit_event_feedback", event_id="evt_ai_001", rating=5, comments="   ")
    with db() as session:
        assert session.scalar(select(EventFeedback.comments)) is None


@pytest.mark.parametrize("rating", [0, 6, -1, "5", True, None, 4.5])
def test_the_rating_must_be_a_whole_number_from_one_to_five(db, set_now, rating):
    register_through_approval(ASHA_PROFILE)
    set_now(AFTER)
    assert "from 1" in refused(ASHA_PROFILE, "submit_event_feedback", event_id="evt_ai_001", rating=rating)


def test_comments_have_a_length_limit_and_a_type(db, set_now):
    register_through_approval(ASHA_PROFILE)
    set_now(AFTER)
    assert "up to 1000" in refused(ASHA_PROFILE, "submit_event_feedback", event_id="evt_ai_001", rating=3, comments="x" * 1001)
    assert "up to 1000" in refused(ASHA_PROFILE, "submit_event_feedback", event_id="evt_ai_001", rating=3, comments=["a"])


def test_only_attendees_can_give_feedback_and_only_after_the_event(db, set_now):
    set_now(AFTER)
    assert "registered for" in refused(ASHA_PROFILE, "submit_event_feedback", event_id="evt_ai_001", rating=5)
    register_through_approval(ASHA_PROFILE)
    set_now(BEFORE)
    assert "hasn't happened" in refused(ASHA_PROFILE, "submit_event_feedback", event_id="evt_ai_001", rating=5)


def test_the_database_allows_one_feedback_per_student_per_event(db, set_now, monkeypatch):
    register_through_approval(ASHA_PROFILE)
    set_now(AFTER)
    act(ASHA_PROFILE, "submit_event_feedback", event_id="evt_ai_001", rating=5)
    monkeypatch.setattr(svc, "check_feedback", lambda *a: None)
    with pytest.raises(ValueError, match="already given"):
        svc.submit_feedback(ASHA, "evt_ai_001", 4, None)


def test_the_database_allows_one_waitlist_place_per_student_per_event(db, set_now, monkeypatch):
    act(RAVI_PROFILE, "join_event_waitlist", event_id="evt_web_002")
    monkeypatch.setattr(svc, "check_waitlist", lambda *a: None)
    with pytest.raises(ValueError, match="already on the waitlist"):
        svc.join_waitlist(RAVI, "evt_web_002")


# --- as tools for the model


def test_the_event_tools_are_registered_bound_to_the_login_and_never_take_a_student_id():
    from app.agent.tool_registry import STUDENT_TOOLS, TOOL_FUNCTIONS, TOOL_SCHEMAS
    from app.actions.registry import ACTIONS

    for name in ("get_event_detail", "get_my_registrations", "get_event_feedback_form"):
        assert name in TOOL_FUNCTIONS and name in STUDENT_TOOLS
        props = next(t for t in TOOL_SCHEMAS if t["function"]["name"] == name)["function"]["parameters"]["properties"]
        assert "student_id" not in props
    for name in ("cancel_event_registration", "join_event_waitlist", "submit_event_feedback"):
        assert name in ACTIONS and name not in TOOL_FUNCTIONS


def test_the_tools_run_through_the_agent_for_the_signed_in_student_only(db, set_now, use_fakes):
    import json

    from fakes import completion, tool_call
    from app.agent import agent

    register_through_approval(ASHA_PROFILE)
    summaries = {}
    for name, args in (("get_event_detail", {"event_id": "evt_ai_001"}), ("get_my_registrations", {"student_id": RAVI}), ("get_event_feedback_form", {"event_id": "evt_ai_001"})):
        client = use_fakes(completion(tool_calls=[tool_call("c1", name, args)]), completion(content="ok"))
        seen = {}
        original = client._create
        client.chat.completions.create = lambda **kw: (seen.update(m=kw["messages"]), original(**kw))[1]
        response = agent.run_agent("q", [], ASHA_PROFILE)
        summaries[name] = response.toolActivity[0].resultSummary
        result = json.loads(next(m for m in seen["m"] if m["role"] == "tool")["content"])
        if name == "get_my_registrations":
            assert [r["event_id"] for r in result["registrations"]] == ["evt_ai_001"], "the model-supplied student id must be ignored"
    assert summaries == {
        "get_event_detail": "AI Workshop: 5 seats left",
        "get_my_registrations": "1 registrations, 0 waitlisted",
        "get_event_feedback_form": "Feedback not available",
    }
