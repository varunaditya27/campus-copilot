from types import SimpleNamespace

import groq
import httpx
import openai
import pytest
from fastapi.testclient import TestClient

from app.agent import agent
from app.core import config
from app.core.errors import AppError
from app.llm import BaseLLMClient, LLMConfigError, get_llm_client
from app.llm.base import Completion, LLMChunk, ToolCallPart, Usage, collect
from app.llm.openai_compatible import OpenAICompatibleClient
from app.llm.providers import GroqLLMClient, OllamaLLMClient, OpenAILLMClient
from app.llm.tiers import tier_for
from app.main import app
from fakes import FakeGroq, RaisingGroq, _chunk, _chunks, fake_llm
from fakes import completion as _completion
from fakes import tool_call as _tool_call
from helpers import ASHA_PROFILE, sign_up

MODELS = {"fast": "m-fast", "balanced": "m-balanced", "best": "m-best"}
MESSAGES = [{"role": "user", "content": "hi"}]
REQUEST = httpx.Request("POST", "http://x")


class Recording:
    """A fake SDK client that records each request and answers from a script."""

    def __init__(self, *replies, usage=None):
        self.requests = []
        self._replies = list(replies) or [_completion(content="ok")]
        self._usage = usage
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.requests.append(kwargs)
        reply = self._replies[min(len(self.requests) - 1, len(self._replies) - 1)]
        chunks = list(_chunks(reply))
        if self._usage:
            chunks.insert(-1, self._usage)
        return iter(chunks)


def client_for(raw, sdk=groq, stream_usage=False):
    return OpenAICompatibleClient("test", raw, sdk, MODELS, stream_usage=stream_usage)


# --- putting a stream back together


def test_text_and_split_tool_calls_are_reassembled_in_order():
    chunks = [
        LLMChunk(text="Hel"),
        LLMChunk(text="lo", tool_call_parts=(ToolCallPart(1, id="b", name="second", arguments='{"x"'),)),
        LLMChunk(tool_call_parts=(ToolCallPart(0, id="a", name="first", arguments='{"y":'),)),
        LLMChunk(tool_call_parts=(ToolCallPart(1, arguments=": 1}"), ToolCallPart(0, arguments=" 2}"))),
    ]
    seen = []
    done = collect(chunks, on_text=seen.append)
    assert done.text == "Hello" and seen == ["Hel", "lo"]
    assert done.tool_calls == [
        {"id": "a", "name": "first", "arguments": '{"y": 2}'},
        {"id": "b", "name": "second", "arguments": '{"x": 1}'},
    ]


def test_a_tool_call_without_an_id_gets_one():
    done = collect([LLMChunk(tool_call_parts=(ToolCallPart(0, name="t", arguments="{}"),))])
    assert done.tool_calls[0]["id"] == "call_0"


def test_the_last_usage_report_wins_and_nothing_means_none():
    assert collect([LLMChunk(usage=Usage(1, 2)), LLMChunk(usage=Usage(5, 6))]).usage == Usage(5, 6)
    assert collect([LLMChunk(text="x")]).usage is None


# --- the shared client


def test_each_tier_asks_for_its_own_model():
    raw = Recording()
    client = client_for(raw)
    for tier in ("fast", "balanced", "best"):
        client.chat_completion(MESSAGES, tier=tier)
    assert [r["model"] for r in raw.requests] == ["m-fast", "m-balanced", "m-best"]


def test_tools_are_sent_only_when_given_and_tool_choice_never_is():
    raw = Recording()
    client = client_for(raw)
    client.chat_completion(MESSAGES)
    client.chat_completion(MESSAGES, tools=[{"type": "function", "function": {"name": "t"}}])
    assert "tools" not in raw.requests[0] and raw.requests[1]["tools"][0]["function"]["name"] == "t"
    assert all("tool_choice" not in r and r["stream"] is True for r in raw.requests)


def test_usage_is_requested_only_from_services_that_support_it():
    plain, asking = Recording(), Recording()
    client_for(plain).chat_completion(MESSAGES)
    client_for(asking, stream_usage=True).chat_completion(MESSAGES)
    assert "stream_options" not in plain.requests[0] and asking.requests[0]["stream_options"] == {"include_usage": True}


def test_usage_is_read_from_either_place_it_may_appear():
    on_chunk = SimpleNamespace(choices=[], usage=SimpleNamespace(prompt_tokens=10, completion_tokens=4))
    nested = SimpleNamespace(choices=[], usage=None, x_groq=SimpleNamespace(usage=SimpleNamespace(prompt_tokens=7, completion_tokens=3)))
    assert client_for(Recording(usage=on_chunk)).chat_completion(MESSAGES).usage == Usage(10, 4)
    assert client_for(Recording(usage=nested)).chat_completion(MESSAGES).usage == Usage(7, 3)
    assert client_for(Recording()).chat_completion(MESSAGES).usage is None


def test_a_malformed_usage_is_ignored():
    odd = SimpleNamespace(choices=[], usage=SimpleNamespace(prompt_tokens="many", completion_tokens=None))
    assert client_for(Recording(usage=odd)).chat_completion(MESSAGES).usage is None


def test_chat_completion_and_tool_call_are_built_on_the_stream():
    raw = Recording(_completion(content="thinking", tool_calls=[_tool_call("c1", "get_cgpa", {})]))
    done = client_for(raw).chat_completion(MESSAGES)
    assert isinstance(done, Completion) and done.text == "thinking" and done.tool_calls[0]["name"] == "get_cgpa"
    assert client_for(Recording(_completion(content="just text"))).tool_call(MESSAGES, []) == []
    assert client_for(raw).tool_call(MESSAGES, [{"type": "function"}])[0]["id"] == "c1"


# --- turning a provider's failures into the application's


@pytest.mark.parametrize("sdk", [groq, openai])
def test_failures_become_the_applications_own_errors_for_either_sdk(sdk):
    def error(cls, status, message="x"):
        return cls(message, response=httpx.Response(status, request=REQUEST), body=None)

    cases = [
        (error(sdk.RateLimitError, 429), 429, "rate_limited"),
        (error(sdk.APIStatusError, 413), 413, "context_too_long"),
        (error(sdk.BadRequestError, 400, "Please reduce the length of the messages"), 413, "context_too_long"),
        (error(sdk.BadRequestError, 400, "maximum context length is 8192 tokens"), 413, "context_too_long"),
        (error(sdk.BadRequestError, 400, "invalid tool schema"), 502, "llm_unavailable"),
        (sdk.APIConnectionError(request=REQUEST), 502, "llm_unavailable"),
    ]
    for exc, status, code in cases:
        with pytest.raises(AppError) as info:
            client_for(RaisingGroq(exc), sdk=sdk).chat_completion(MESSAGES)
        assert (info.value.status_code, info.value.error_code) == (status, code), exc


def test_a_failure_in_the_middle_of_a_stream_is_mapped_too():
    from fakes import FailingStreamGroq

    with pytest.raises(AppError) as info:
        list(client_for(FailingStreamGroq(groq.APIConnectionError(request=REQUEST))).stream_completion(MESSAGES))
    assert info.value.error_code == "llm_unavailable"


def test_an_exception_that_is_not_the_sdks_is_not_swallowed():
    with pytest.raises(ZeroDivisionError):
        client_for(RaisingGroq(ZeroDivisionError())).chat_completion(MESSAGES)


# --- the abstraction itself


def test_a_provider_must_implement_the_two_essentials():
    with pytest.raises(TypeError):
        BaseLLMClient()

    class Half(BaseLLMClient):
        provider = "half"

    with pytest.raises(TypeError):
        Half()


class Scripted(BaseLLMClient):
    """A provider that is not an OpenAI-style service at all, to show the agent only needs the base class."""

    provider = "scripted"

    def __init__(self):
        self.asked = []

    def model_for(self, tier):
        return f"scripted-{tier}"

    def stream_completion(self, messages, tools=None, tier="balanced"):
        self.asked.append((tier, bool(tools)))
        yield LLMChunk(text="from a ")
        yield LLMChunk(text="different provider")


def test_the_agent_runs_on_any_provider_that_implements_the_base_class(db, monkeypatch):
    scripted = Scripted()
    monkeypatch.setattr(agent, "get_llm_client", lambda: scripted)
    monkeypatch.setattr(agent, "retrieve", lambda m: [])
    response = agent.run_agent("hello", [], ASHA_PROFILE)
    assert response.reply == "from a different provider" and scripted.asked == [("balanced", True)]


# --- choosing and configuring a provider


@pytest.fixture
def settings(monkeypatch):
    def apply(**values):
        defaults = dict(
            LLM_PROVIDER="groq", LLM_MODEL="", LLM_MODEL_FAST="", LLM_MODEL_BEST="", GROQ_MODEL="openai/gpt-oss-120b",
            OLLAMA_BASE_URL="http://localhost:11434/v1", OPENAI_API_KEY="", OPENAI_BASE_URL="", GROQ_API_KEY="k",
        )
        for name, value in {**defaults, **values}.items():
            monkeypatch.setattr(config, name, value)
        get_llm_client.cache_clear()

    yield apply
    get_llm_client.cache_clear()


def test_groq_is_the_default_and_uses_current_production_models(settings):
    client = get_llm_client()
    assert isinstance(client, GroqLLMClient) and client.provider == "groq"
    assert [client.model_for(t) for t in ("fast", "balanced", "best")] == ["openai/gpt-oss-20b", "openai/gpt-oss-120b", "openai/gpt-oss-120b"]


def test_the_older_groq_model_setting_still_works_and_llm_model_overrides_it(settings):
    settings(GROQ_MODEL="openai/gpt-oss-20b")
    assert get_llm_client().model_for("balanced") == "openai/gpt-oss-20b"
    settings(GROQ_MODEL="openai/gpt-oss-20b", LLM_MODEL="custom")
    assert get_llm_client().model_for("balanced") == "custom"


def test_each_tier_can_be_set(settings):
    settings(LLM_MODEL="b", LLM_MODEL_FAST="f", LLM_MODEL_BEST="x")
    client = get_llm_client()
    assert [client.model_for(t) for t in ("fast", "balanced", "best")] == ["f", "b", "x"]


def test_unset_tiers_fall_back_to_the_balanced_model(settings):
    settings(LLM_PROVIDER="ollama", LLM_MODEL="llama-x")
    client = get_llm_client()
    assert isinstance(client, OllamaLLMClient)
    assert {client.model_for(t) for t in ("fast", "balanced", "best")} == {"llama-x"}


def test_ollama_talks_to_the_local_server_with_a_placeholder_key(settings):
    settings(LLM_PROVIDER="ollama", LLM_MODEL="m", OLLAMA_BASE_URL="http://gpu-box:11434/v1")
    raw = get_llm_client()._raw
    assert isinstance(raw, openai.OpenAI) and str(raw.base_url).startswith("http://gpu-box:11434/v1") and raw.api_key == "ollama"


def test_openai_uses_its_key_and_an_optional_compatible_base_url(settings):
    settings(LLM_PROVIDER="openai", LLM_MODEL="some-model", OPENAI_API_KEY="sk-test", OPENAI_BASE_URL="https://llm.example/v1")
    client = get_llm_client()
    assert isinstance(client, OpenAILLMClient) and client._raw.api_key == "sk-test" and str(client._raw.base_url).startswith("https://llm.example/v1")


@pytest.mark.parametrize("provider", ["ollama", "openai"])
def test_providers_without_default_models_demand_one(settings, provider):
    settings(LLM_PROVIDER=provider)
    with pytest.raises(LLMConfigError, match="LLM_MODEL is required"):
        get_llm_client()


def test_a_missing_key_is_a_clear_error_unless_a_server_of_your_own_is_named(settings):
    settings(GROQ_API_KEY="")
    with pytest.raises(LLMConfigError, match="GROQ_API_KEY is not set"):
        get_llm_client()
    settings(LLM_PROVIDER="openai", LLM_MODEL="m")
    with pytest.raises(LLMConfigError, match="OPENAI_API_KEY is not set"):
        get_llm_client()
    settings(LLM_PROVIDER="openai", LLM_MODEL="m", OPENAI_BASE_URL="http://localhost:8000/v1")
    assert get_llm_client()._raw.api_key == "unused"


def test_an_unknown_provider_is_a_clear_error(settings):
    settings(LLM_PROVIDER="skynet")
    with pytest.raises(LLMConfigError, match="must be one of groq, openai, ollama"):
        get_llm_client()


def test_the_client_is_built_once(settings):
    assert get_llm_client() is get_llm_client()


# --- quality tiers


@pytest.mark.parametrize(
    "requested, agentic, expected",
    [(None, False, "balanced"), (None, True, "best"), ("fast", True, "fast"), ("best", False, "best"), ("balanced", True, "balanced"), ("nonsense", False, "balanced")],
)
def test_the_tier_follows_the_request_or_the_kind_of_task(requested, agentic, expected):
    assert tier_for(requested, agentic) == expected


def run_with(monkeypatch, replies, quality=None, message="hi"):
    raw = Recording(*replies)
    monkeypatch.setattr(agent, "get_llm_client", lambda: fake_llm(raw))
    monkeypatch.setattr(agent, "retrieve", lambda m: [])
    agent.run_agent(message, [], ASHA_PROFILE, quality=quality)
    return [r["model"] for r in raw.requests]


def test_an_ordinary_question_uses_the_balanced_model(db, monkeypatch):
    assert run_with(monkeypatch, [_completion(content="hello")]) == ["balanced-model"]


def test_once_tools_have_run_the_follow_up_uses_the_best_model(db, monkeypatch):
    replies = [_completion(tool_calls=[_tool_call("c1", "get_cgpa", {})]), _completion(content="done")]
    assert run_with(monkeypatch, replies) == ["balanced-model", "best-model"]


def test_a_requested_tier_is_used_for_every_round(db, monkeypatch):
    replies = [_completion(tool_calls=[_tool_call("c1", "get_cgpa", {})]), _completion(content="done")]
    assert run_with(monkeypatch, replies, quality="fast") == ["fast-model", "fast-model"]


def test_a_plan_makes_the_task_agentic(db, monkeypatch):
    monkeypatch.setattr(agent, "_graph", agent.build_graph(planning=True))
    replies = [_completion(content='["find the event", "register"]'), _completion(content="done")]
    assert run_with(monkeypatch, replies) == ["balanced-model", "best-model"]


def test_the_quality_can_be_chosen_in_the_chat_request(db, monkeypatch):
    raw = Recording(_completion(content="hello"))
    monkeypatch.setattr(agent, "get_llm_client", lambda: fake_llm(raw))
    monkeypatch.setattr(agent, "retrieve", lambda m: [])
    client = sign_up(TestClient(app))
    assert client.post("/api/chat", json={"message": "hi", "quality": "best"}).status_code == 200
    assert raw.requests[0]["model"] == "best-model"
    assert client.post("/api/chat", json={"message": "hi", "quality": "ludicrous"}).status_code == 422


def test_the_router_uses_the_fast_model(db, monkeypatch):
    from app.agent import supervisor

    raw = Recording(_completion(content='["general"]'), _completion(content="hello"))
    monkeypatch.setattr(agent, "get_llm_client", lambda: fake_llm(raw))
    monkeypatch.setattr(agent, "retrieve", lambda m: [])
    monkeypatch.setattr(supervisor, "MULTI_AGENT", True)
    list(supervisor.run_agent_stream("hi", [], ASHA_PROFILE))
    assert [r["model"] for r in raw.requests] == ["fast-model", "balanced-model"]
