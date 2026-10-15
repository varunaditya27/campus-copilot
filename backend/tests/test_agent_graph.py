import threading
import time

import pytest
from langgraph.errors import GraphRecursionError

from app.agent import agent
from app.agent.agent import (
    AgentState,
    build_graph,
    is_confirmation_needed,
    is_done,
    route_after_reason,
    route_after_tools,
    should_call_tools,
)
from fakes import SlowGroq
from fakes import fake_llm
from fakes import completion as _completion
from fakes import tool_call as _tool_call
from helpers import ASHA_PROFILE


def state(**fields):
    return AgentState(message="hi", student=ASHA_PROFILE, **fields)


def call(name="search_events", call_id="c1"):
    return {"id": call_id, "name": name, "arguments": "{}"}


# --- the shape of the graph


def test_the_graph_has_the_planned_nodes():
    nodes = set(build_graph(planning=False).get_graph().nodes) - {"__start__", "__end__"}
    assert nodes == {"retrieve", "reason", "execute_tools", "request_confirmation", "respond"}


def test_planning_adds_one_node_between_retrieving_and_reasoning():
    graph = build_graph(planning=True).get_graph()
    assert "plan" in graph.nodes
    edges = {(e.source, e.target) for e in graph.edges}
    assert ("retrieve", "plan") in edges and ("plan", "reason") in edges and ("retrieve", "reason") not in edges


def test_planning_is_off_unless_asked_for():
    assert "plan" not in agent._graph.get_graph().nodes


# --- the decisions


def test_asking_to_register_needs_a_confirmation():
    assert is_confirmation_needed(state(tool_calls=[call("register_for_event")]))
    assert is_confirmation_needed(state(tool_calls=[call(), call("register_for_event")]))
    assert not is_confirmation_needed(state(tool_calls=[call()]))


def test_tools_are_called_only_when_the_model_asked():
    assert should_call_tools(state(tool_calls=[call()])) and not should_call_tools(state())


def test_a_reply_means_done_even_when_it_is_empty():
    assert is_done(state(reply="x")) and is_done(state(reply="")) and not is_done(state())


def test_the_model_answer_goes_to_respond():
    assert route_after_reason(state(reply="done")) == "respond"


def test_tool_calls_go_to_the_tools():
    assert route_after_reason(state(tool_calls=[call()])) == "execute_tools"


def test_a_registration_goes_to_confirmation_not_the_tools():
    assert route_after_reason(state(tool_calls=[call(), call("register_for_event")])) == "request_confirmation"


def test_after_tools_the_model_gets_another_turn_unless_the_rounds_are_used_up():
    assert route_after_tools(state()) == "reason"
    assert route_after_tools(state(reply=agent.OUT_OF_ROUNDS_REPLY)) == "respond"


# --- parallel tools


def test_tool_calls_in_one_round_run_at_the_same_time(use_fakes, monkeypatch):
    barrier = threading.Barrier(2, timeout=5)  # both must arrive together, or this raises

    def meet(**kwargs):
        barrier.wait()
        return {"percentage": 50.0}

    monkeypatch.setitem(agent.TOOL_FUNCTIONS, "calculate_attendance", meet)
    use_fakes(
        _completion(tool_calls=[
            _tool_call("a", "calculate_attendance", {"attended": 1, "total": 2}),
            _tool_call("b", "calculate_attendance", {"attended": 3, "total": 6}),
        ]),
        _completion(content="Both are 50%."),
    )

    response = agent.run_agent("two sums", [], ASHA_PROFILE)

    assert [a.status for a in response.toolActivity] == ["done", "done"]
    assert response.reply == "Both are 50%."


def test_parallel_results_keep_the_order_of_the_calls_but_events_follow_completion(use_fakes, monkeypatch):
    def slow(**kwargs):
        time.sleep(0.2)
        return {"percentage": 1.0}

    def fast(**kwargs):
        return {"available": True, "remaining_seats": 3}

    monkeypatch.setitem(agent.TOOL_FUNCTIONS, "calculate_attendance", slow)
    monkeypatch.setitem(agent.TOOL_FUNCTIONS, "check_event_availability", fast)
    client = use_fakes(
        _completion(tool_calls=[
            _tool_call("first", "calculate_attendance", {"attended": 1, "total": 2}),
            _tool_call("second", "check_event_availability", {"event_id": "x"}),
        ]),
        _completion(content="ok"),
    )
    seen = {}
    original = client._create

    def spy(**kwargs):
        seen["messages"] = kwargs["messages"]
        return original(**kwargs)

    client.chat.completions.create = spy

    events = list(agent.run_agent_stream("go", [], ASHA_PROFILE))

    done_order = [e["payload"]["id"] for e in events if e["type"] == "tool_done"]
    started = [e["payload"]["id"] for e in events if e["type"] == "tool_start"]
    assert started == ["first", "second"] and done_order == ["second", "first"]
    assert [a["id"] for a in events[-1]["payload"]["toolActivity"]] == ["first", "second"]
    tool_messages = [m["tool_call_id"] for m in seen["messages"] if m["role"] == "tool"]
    assert tool_messages == ["first", "second"]
    types = [e["type"] for e in events]
    assert types.index("tool_start") < max(i for i, t in enumerate(types) if t == "tool_start") < types.index("tool_done")


def test_a_failing_tool_among_several_does_not_stop_the_others(db, use_fakes, monkeypatch):
    def boom(**kwargs):
        raise ValueError("bad")

    monkeypatch.setitem(agent.TOOL_FUNCTIONS, "calculate_attendance", boom)
    use_fakes(
        _completion(tool_calls=[
            _tool_call("a", "calculate_attendance", {"attended": 1, "total": 2}),
            _tool_call("b", "check_event_availability", {"event_id": "nope"}),
        ]),
        _completion(content="done"),
    )
    response = agent.run_agent("x", [], ASHA_PROFILE)
    assert [a.status for a in response.toolActivity] == ["error", "done"]


# --- events are live


def test_tokens_arrive_while_the_model_is_still_talking(monkeypatch):
    slow = SlowGroq(["one", "two", "three", "four"], pause=0.1)
    monkeypatch.setattr(agent, "get_llm_client", lambda: fake_llm(slow))
    monkeypatch.setattr(agent, "retrieve", lambda message: [])

    first_token_at = None
    for event in agent.run_agent_stream("hi", [], ASHA_PROFILE):
        if event["type"] == "token" and first_token_at is None:
            first_token_at = time.monotonic()

    assert slow.finished_at is not None
    assert slow.finished_at - first_token_at > 0.15, "the first token should not wait for the whole reply"


# --- the model keeps its own words before a tool call


def test_text_written_before_a_tool_call_stays_in_the_conversation(use_fakes):
    client = use_fakes(
        _completion(content="Let me check.", tool_calls=[_tool_call("c1", "calculate_attendance", {"attended": 1, "total": 2})]),
        _completion(content="50%"),
    )
    seen = {}
    original = client._create

    def spy(**kwargs):
        seen["messages"] = kwargs["messages"]
        return original(**kwargs)

    client.chat.completions.create = spy
    agent.run_agent("x", [], ASHA_PROFILE)

    assistant = [m for m in seen["messages"] if m["role"] == "assistant" and "tool_calls" in m]
    assert assistant[0]["content"] == "Let me check."


# --- the safety net


def test_a_run_that_takes_too_many_steps_is_stopped(use_fakes, monkeypatch):
    use_fakes(_completion(tool_calls=[_tool_call("c1", "calculate_attendance", {"attended": 1, "total": 2})]))
    monkeypatch.setattr(agent, "RECURSION_LIMIT", 3)
    with pytest.raises(GraphRecursionError):
        agent.run_agent("loop", [], ASHA_PROFILE)


def test_the_normal_round_limit_stops_a_run_before_the_safety_net(use_fakes):
    client = use_fakes(_completion(tool_calls=[_tool_call("c1", "calculate_attendance", {"attended": 1, "total": 2})]))
    response = agent.run_agent("loop", [], ASHA_PROFILE)
    assert client.calls == agent.MAX_TOOL_ROUNDS and response.reply == agent.OUT_OF_ROUNDS_REPLY


def test_the_safety_net_leaves_room_for_every_allowed_round():
    assert agent.RECURSION_LIMIT >= agent.MAX_TOOL_ROUNDS * 2 + 3


# --- runs do not leak into each other


def test_each_run_starts_with_a_clean_state(use_fakes):
    use_fakes(
        _completion(tool_calls=[_tool_call("c1", "calculate_attendance", {"attended": 1, "total": 2})]),
        _completion(content="first"),
        _completion(content="second"),
    )
    first = agent.run_agent("one", [], ASHA_PROFILE)
    second = agent.run_agent("two", [], ASHA_PROFILE)

    assert first.toolActivity and second.toolActivity is None
    assert second.reply == "second"


# --- planning (switched on for these tests)


@pytest.fixture
def planning(monkeypatch):
    monkeypatch.setattr(agent, "_graph", build_graph(planning=True))


def run_with_plan(use_fakes, plan_reply, answer="final answer"):
    client = use_fakes(_completion(content=plan_reply), _completion(content=answer))
    calls = []
    original = client._create

    def spy(**kwargs):
        calls.append(kwargs)
        return original(**kwargs)

    client.chat.completions.create = spy
    response = agent.run_agent("find an event and register me", [], ASHA_PROFILE)
    return response, calls


def test_a_plan_is_shown_to_the_model_before_it_answers(planning, use_fakes):
    response, calls = run_with_plan(use_fakes, '["find a matching event", "check there are seats"]')

    assert response.reply == "final answer" and len(calls) == 2
    system_text = " ".join(m["content"] for m in calls[1]["messages"] if m["role"] == "system")
    assert "1. find a matching event" in system_text and "2. check there are seats" in system_text


def test_the_planning_call_offers_no_tools(planning, use_fakes):
    _, calls = run_with_plan(use_fakes, "[]")
    assert "tools" not in calls[0] and "tools" in calls[1]


def test_the_planner_sees_only_the_students_request(planning, use_fakes):
    _, calls = run_with_plan(use_fakes, "[]")
    assert [m["role"] for m in calls[0]["messages"]] == ["system", "user"]
    assert calls[0]["messages"][1]["content"] == "find an event and register me"


@pytest.mark.parametrize("plan_reply", ["[]", "not json", '"just a string"', '{"a": 1}', '[1, 2]', '["", "  "]', ""])
def test_no_usable_plan_means_no_plan_message(planning, use_fakes, plan_reply):
    response, calls = run_with_plan(use_fakes, plan_reply)
    assert response.reply == "final answer"
    assert not any("Plan for this request" in m["content"] for m in calls[1]["messages"] if m["role"] == "system")


def test_a_plan_is_trimmed_to_a_sensible_size():
    steps = agent._parse_plan('["' + '", "'.join(f"step {i}" for i in range(20)) + '"]')
    assert len(steps) == 6
    assert len(agent._parse_plan('["' + "x" * 500 + '"]')[0]) == 200
    assert agent._parse_plan('["a", 3, "b"]') == ["a", "b"]


def test_without_planning_only_one_model_call_is_made(use_fakes):
    client = use_fakes(_completion(content="answer"))
    agent.run_agent("hi", [], ASHA_PROFILE)
    assert client.calls == 1


def test_a_plan_does_not_change_the_event_stream(planning, use_fakes):
    use_fakes(_completion(content='["one step"]'), _completion(content="answer"))
    types = [e["type"] for e in agent.run_agent_stream("x", [], ASHA_PROFILE)]
    assert types[0] == "rag_context" and types[-1] == "done" and "plan" not in types
