import json
from types import SimpleNamespace

import pytest

from app.agent import agent
from app.models.chat import ChatHistoryItem
from helpers import read_json


def _tool_call(call_id, name, args):
    call = SimpleNamespace(
        id=call_id,
        function=SimpleNamespace(name=name, arguments=json.dumps(args)),
    )
    call.model_dump = lambda: {
        "id": call_id,
        "type": "function",
        "function": {"name": name, "arguments": json.dumps(args)},
    }
    return call


def _completion(content=None, tool_calls=None):
    message = SimpleNamespace(content=content, tool_calls=tool_calls)
    return SimpleNamespace(choices=[SimpleNamespace(message=message)])


class FakeGroq:
    """Returns the scripted completions in order; repeats the last one forever."""

    def __init__(self, *completions):
        self._completions = list(completions)
        self.calls = 0
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        index = min(self.calls, len(self._completions) - 1)
        self.calls += 1
        return self._completions[index]


@pytest.fixture
def use_fakes(monkeypatch):
    def install(*completions, chunks=()):
        client = FakeGroq(*completions)
        monkeypatch.setattr(agent, "get_groq_client", lambda: client)
        monkeypatch.setattr(agent, "retrieve", lambda message: list(chunks))
        return client

    return install


def test_plain_reply_without_tools(use_fakes):
    use_fakes(_completion(content="Hello there"))

    response = agent.run_agent("hi", [])

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

    agent.run_agent("second", [ChatHistoryItem(role="user", content="first")])

    contents = [m["content"] for m in seen["messages"]]
    assert contents[-2:] == ["first", "second"]


def test_tool_call_then_reply_fills_activity_log(use_fakes):
    use_fakes(
        _completion(tool_calls=[_tool_call("c1", "calculate_attendance", {"attended": 45, "total": 60})]),
        _completion(content="You are at 75%."),
    )

    response = agent.run_agent("what's my attendance?", [])

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

    response = agent.run_agent("x", [])

    assert response.toolActivity[0].status == "error"
    assert response.toolActivity[0].resultSummary == "bad input"


def test_register_returns_confirmation_and_does_not_register(data_files, use_fakes):
    use_fakes(
        _completion(tool_calls=[_tool_call("c1", "register_for_event", {"event_id": "evt_ai_001", "student_id": "1RV23IS101"})]),
    )
    events_before = read_json(data_files["events"])

    response = agent.run_agent("register me", [])

    assert response.confirmation.event.id == "evt_ai_001"
    assert response.confirmation.studentId == "1RV23IS101"
    assert "confirm" in response.reply.lower()
    assert read_json(data_files["registrations"]) == []
    assert read_json(data_files["events"]) == events_before


def test_register_for_unknown_event_gives_fallback_text(data_files, use_fakes):
    use_fakes(
        _completion(tool_calls=[_tool_call("c1", "register_for_event", {"event_id": "nope", "student_id": "1RV23IS101"})]),
    )

    response = agent.run_agent("register me", [])

    assert response.confirmation is None
    assert "couldn't find that event" in response.reply


def test_stops_after_max_tool_rounds(use_fakes):
    endless = _completion(tool_calls=[_tool_call("c1", "calculate_attendance", {"attended": 1, "total": 2})])
    client = use_fakes(endless)

    response = agent.run_agent("loop forever", [])

    assert client.calls == agent.MAX_TOOL_ROUNDS
    assert "wasn't able to finish" in response.reply
    assert len(response.toolActivity) == agent.MAX_TOOL_ROUNDS


def test_retrieved_chunks_become_sources(use_fakes):
    chunk = {"document": "policies.md", "section": "Leave", "snippet": "Apply 3 days ahead."}
    use_fakes(_completion(content="See policy."), chunks=[chunk])

    response = agent.run_agent("leave policy?", [])

    assert len(response.sources) == 1
    assert response.sources[0].model_dump() == chunk
