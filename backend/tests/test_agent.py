from app.agent import agent
from app.models.chat import ChatHistoryItem
from fakes import completion as _completion
from fakes import tool_call as _tool_call
from helpers import ASHA_PROFILE, all_registrations, event_registered


def test_plain_reply_without_tools(use_fakes):
    use_fakes(_completion(content="Hello there"))

    response = agent.run_agent("hi", [], ASHA_PROFILE)

    assert response.reply == "Hello there"
    assert response.toolActivity is None
    assert response.confirmation is None


def test_history_is_sent_to_the_model(monkeypatch, use_fakes):
    client = use_fakes(_completion(content="ok"))
    seen = {}
    original = client._create

    def spy(**kwargs):
        seen["messages"] = kwargs["messages"]
        return original(**kwargs)

    client.chat.completions.create = spy

    agent.run_agent("second", [ChatHistoryItem(role="user", content="first")], ASHA_PROFILE)

    contents = [m["content"] for m in seen["messages"]]
    assert contents[-2:] == ["first", "second"]


def test_tool_call_then_reply_fills_activity_log(use_fakes):
    use_fakes(
        _completion(tool_calls=[_tool_call("c1", "calculate_attendance", {"attended": 45, "total": 60})]),
        _completion(content="You are at 75%."),
    )

    response = agent.run_agent("what's my attendance?", [], ASHA_PROFILE)

    assert response.reply == "You are at 75%."
    assert len(response.toolActivity) == 1
    entry = response.toolActivity[0]
    assert (entry.id, entry.tool, entry.status) == ("c1", "calculate_attendance", "done")
    assert entry.resultSummary == "75.0% attendance"


def test_tool_that_raises_is_logged_as_error(monkeypatch, use_fakes):
    def boom(**kwargs):
        raise ValueError("bad input")

    monkeypatch.setitem(agent.TOOL_FUNCTIONS, "calculate_attendance", boom)
    use_fakes(
        _completion(tool_calls=[_tool_call("c1", "calculate_attendance", {"attended": 1, "total": 2})]),
        _completion(content="Sorry."),
    )

    response = agent.run_agent("x", [], ASHA_PROFILE)

    assert response.toolActivity[0].status == "error"
    assert response.toolActivity[0].resultSummary == "bad input"


def test_register_returns_confirmation_and_does_not_register(db, use_fakes):
    use_fakes(
        _completion(tool_calls=[_tool_call("c1", "register_for_event", {"event_id": "evt_ai_001"})]),
    )

    response = agent.run_agent("register me", [], ASHA_PROFILE)

    confirmation = response.confirmation
    assert (confirmation.action, confirmation.title) == ("register_for_event", "Register for AI Workshop")
    assert {line.label: line.value for line in confirmation.lines}["Student"] == "1RV23IS101"
    assert "confirm" in response.reply.lower()
    assert all_registrations(db) == []
    assert event_registered(db, "evt_ai_001") == 4


def test_register_for_unknown_event_gives_fallback_text(db, use_fakes):
    use_fakes(
        _completion(tool_calls=[_tool_call("c1", "register_for_event", {"event_id": "nope"})]),
    )

    response = agent.run_agent("register me", [], ASHA_PROFILE)

    assert response.confirmation is None
    assert "couldn't find that event" in response.reply


def test_stops_after_max_tool_rounds(use_fakes):
    endless = _completion(tool_calls=[_tool_call("c1", "calculate_attendance", {"attended": 1, "total": 2})])
    client = use_fakes(endless)

    response = agent.run_agent("loop forever", [], ASHA_PROFILE)

    assert client.calls == agent.MAX_TOOL_ROUNDS
    assert "wasn't able to finish" in response.reply
    assert len(response.toolActivity) == agent.MAX_TOOL_ROUNDS


def test_retrieved_chunks_become_sources(use_fakes):
    chunk = {"document": "policies.md", "section": "Leave", "snippet": "Apply 3 days ahead."}
    use_fakes(_completion(content="See policy."), chunks=[chunk])

    response = agent.run_agent("leave policy?", [], ASHA_PROFILE)

    assert len(response.sources) == 1
    assert response.sources[0].model_dump() == chunk
