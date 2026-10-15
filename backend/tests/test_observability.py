import io
import json
import logging

import pytest
import structlog
from fastapi import FastAPI
from fastapi.testclient import TestClient
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from prometheus_client import REGISTRY
from sqlalchemy import text

from app.agent import agent
from app.core import config
from app.core.errors import AppError, register_error_handlers
from app.llm.base import Usage
from app.main import app
from app.observability import context, metrics
from app.observability.logging import configure_logging, get_logger
from app.observability.middleware import RequestLoggingMiddleware
from app.observability.sentry import init_sentry
from app.observability.tracing import setup_tracing
from fakes import FakeGroq, fake_llm
from fakes import completion as _completion
from fakes import tool_call as _tool_call
from helpers import ADMIN, ASHA_PROFILE, add_academic_data, sign_in_as, sign_up


@pytest.fixture
def logs():
    buffer = io.StringIO()
    configure_logging(level="DEBUG", log_format="json", stream=buffer)
    yield lambda: [json.loads(line) for line in buffer.getvalue().splitlines() if line.startswith("{")]
    configure_logging()


def sample(name, **labels):
    return REGISTRY.get_sample_value(name, labels) or 0.0


# --- structured logging


def test_every_line_is_one_json_object_with_the_usual_fields(logs):
    get_logger("demo").info("something.happened", count=3)
    (line,) = [l for l in logs() if l["event"] == "something.happened"]
    assert (line["count"], line["level"], line["logger"]) == (3, "info", "demo")
    assert line["timestamp"].endswith("Z") and "T" in line["timestamp"]


def test_the_standard_librarys_logs_come_out_as_json_too(logs):
    logging.getLogger("some.library").warning("careful %s", "now")
    (line,) = [l for l in logs() if l["logger"] == "some.library"]
    assert (line["event"], line["level"]) == ("careful now", "warning")


def test_an_exception_is_logged_with_its_traceback(logs):
    try:
        1 / 0
    except ZeroDivisionError:
        get_logger("demo").error("failed", exc_info=True)
    (line,) = [l for l in logs() if l["event"] == "failed"]
    assert "ZeroDivisionError" in line["exception"]


def test_the_requests_fields_are_added_to_every_line_logged_while_it_is_handled(logs):
    context.start_request({"request_id": "abc"})
    context.bind(user_id=7)
    get_logger("demo").info("inside")
    context.start_request({})
    assert [l for l in logs() if l["event"] == "inside"][0]["request_id"] == "abc"
    assert [l for l in logs() if l["event"] == "inside"][0]["user_id"] == 7


def test_readable_output_can_be_chosen(monkeypatch):
    buffer = io.StringIO()
    configure_logging(level="INFO", log_format="console", stream=buffer)
    get_logger("demo").info("plain.text", answer=42)
    configure_logging()
    assert "plain.text" in buffer.getvalue() and "answer" in buffer.getvalue() and not buffer.getvalue().startswith("{")


def test_configuring_twice_does_not_duplicate_lines(logs):
    buffer = io.StringIO()
    configure_logging(stream=buffer, log_format="json")
    configure_logging(stream=buffer, log_format="json")
    get_logger("demo").info("once")
    assert buffer.getvalue().count('"once"') == 1


# --- one line per request


@pytest.fixture
def client(db):
    return TestClient(app)


def request_lines(logs):
    return [l for l in logs() if l["event"] == "request"]


def test_a_request_gets_an_id_that_is_returned_and_logged(client, logs):
    response = client.get("/api/events")
    request_id = response.headers["x-request-id"]
    (line,) = request_lines(logs)
    assert len(request_id) == 32 and line["request_id"] == request_id
    assert (line["method"], line["path"], line["status"]) == ("GET", "/api/events", 200) and line["duration_ms"] >= 0


def test_a_sensible_request_id_from_the_caller_is_kept(client, logs):
    response = client.get("/api/events", headers={"X-Request-ID": "trace-me-123"})
    assert response.headers["x-request-id"] == "trace-me-123" and request_lines(logs)[0]["request_id"] == "trace-me-123"


@pytest.mark.parametrize("bad", ["has spaces", "x" * 65, "<script>", "a/b"])
def test_an_odd_request_id_is_replaced_not_logged(client, logs, bad):
    response = client.get("/api/events", headers={"X-Request-ID": bad})
    assert response.headers["x-request-id"] != bad and len(response.headers["x-request-id"]) in (32, 64)
    assert "<script>" not in json.dumps(logs())


def test_the_signed_in_user_is_on_the_request_line(client, logs):
    sign_up(client)
    client.get("/api/chat/history")
    line = [l for l in request_lines(logs) if l["path"] == "/api/chat/history"][0]
    assert (line["role"], line["user_id"]) == ("student", 1)


def test_failed_requests_are_logged_with_their_status(client, logs):
    client.get("/api/chat/history")
    client.get("/api/events/nope")
    assert [l["status"] for l in request_lines(logs)] == [401, 404]


def test_health_checks_do_not_fill_the_log(client, logs):
    client.get("/health")
    assert [l for l in logs() if l["event"] == "request" and l["level"] == "info"] == []
    assert [l for l in logs() if l["event"] == "request" and l["level"] == "debug"][0]["path"] == "/health"


def test_secrets_never_reach_the_log(client, logs):
    sign_up(client)
    client.post("/api/auth/login", json={"email": "asha@example.com", "password": "correct horse battery"})
    text_out = json.dumps(logs())
    assert "correct horse battery" not in text_out and "access_token" not in text_out


def test_a_streamed_reply_is_logged_once_when_it_ends(db, logs, monkeypatch):
    monkeypatch.setattr(agent, "get_llm_client", lambda: fake_llm(FakeGroq(_completion(content="hello there"))))
    monkeypatch.setattr(agent, "retrieve", lambda m: [])
    client = sign_up(TestClient(app))
    with client.stream("POST", "/api/chat/stream", json={"message": "hi"}) as response:
        list(response.iter_lines())
    lines = [l for l in request_lines(logs) if l["path"] == "/api/chat/stream"]
    assert len(lines) == 1 and lines[0]["status"] == 200


def test_an_unhandled_error_is_a_500_with_a_traceback_and_a_request_line(logs):
    broken = FastAPI()
    register_error_handlers(broken)
    broken.add_middleware(RequestLoggingMiddleware)

    @broken.get("/boom")
    def boom():
        raise RuntimeError("kaboom")

    response = TestClient(broken, raise_server_exceptions=False).get("/boom")
    assert response.status_code == 500 and response.json()["error_code"] == "internal_error"
    assert "kaboom" in [l for l in logs() if l["event"] == "unhandled_exception"][0]["exception"]
    assert request_lines(logs)[0]["status"] == 500


# --- agent logs


def run_agent_with_tool(monkeypatch, name="get_cgpa", args=None):
    client = fake_llm(FakeGroq(_completion(tool_calls=[_tool_call("c1", name, args or {})]), _completion(content="done")))
    monkeypatch.setattr(agent, "get_llm_client", lambda: client)
    monkeypatch.setattr(agent, "retrieve", lambda m: [{"document": "d.md", "section": "S", "snippet": "x"}])
    return agent.run_agent("what is my cgpa", [], ASHA_PROFILE)


def test_the_agents_decisions_and_tool_calls_are_logged_without_their_data(db, logs, monkeypatch):
    add_academic_data(db)
    run_agent_with_tool(monkeypatch)
    events = {l["event"]: l for l in logs()}
    assert events["rag.retrieve"]["chunks"] == 1
    assert events["agent.tool"]["tool"] == "get_cgpa" and events["agent.tool"]["status"] == "done"
    reasons = [l for l in logs() if l["event"] == "agent.reason"]
    assert [r["tool_calls"] for r in reasons] == [["get_cgpa"], []] and [r["tier"] for r in reasons] == ["balanced", "best"]
    assert "8.45" not in json.dumps(logs()), "results of tools hold personal data and are not logged"
    assert events["llm.request"]["provider"] == "groq"


# --- metrics


def test_the_metrics_endpoint_serves_prometheus_text_with_request_stats(client):
    client.get("/api/events")
    body = client.get("/metrics").text
    assert "http_request_duration_seconds" in body and 'handler="/api/events"' in body
    assert 'handler="/metrics"' not in body and 'handler="/health"' not in body


def test_tool_calls_and_rounds_are_counted(db, monkeypatch):
    add_academic_data(db)
    before = (sample("agent_tool_calls_total", tool="get_cgpa", status="done"), sample("agent_tool_rounds_total", domain="all"))
    run_agent_with_tool(monkeypatch)
    assert sample("agent_tool_calls_total", tool="get_cgpa", status="done") == before[0] + 1
    assert sample("agent_tool_rounds_total", domain="all") == before[1] + 1
    assert sample("agent_tool_duration_seconds_count", tool="get_cgpa") >= 1


def test_a_tool_name_the_model_invented_cannot_create_new_series(db, monkeypatch):
    run_agent_with_tool(monkeypatch, name="drop_all_tables")
    assert sample("agent_tool_calls_total", tool="unknown", status="error") >= 1
    assert sample("agent_tool_calls_total", tool="drop_all_tables", status="error") == 0


def test_retrieval_latency_and_how_many_passages_came_back_are_recorded(db, monkeypatch):
    before = (sample("rag_retrieval_latency_seconds_count"), sample("rag_chunks_returned_count_count"), sample("rag_chunks_returned_count_sum"))
    run_agent_with_tool(monkeypatch)
    assert sample("rag_retrieval_latency_seconds_count") == before[0] + 1
    assert sample("rag_chunks_returned_count_count") == before[1] + 1 and sample("rag_chunks_returned_count_sum") == before[2] + 1


def test_a_proposed_action_is_counted(db, monkeypatch):
    before = sample("agent_confirmations_requested_total", action="register_for_event")
    monkeypatch.setattr(agent, "get_llm_client", lambda: fake_llm(FakeGroq(_completion(tool_calls=[_tool_call("c1", "register_for_event", {"event_id": "evt_ai_001"})]))))
    monkeypatch.setattr(agent, "retrieve", lambda m: [])
    agent.run_agent("register me", [], ASHA_PROFILE)
    assert sample("agent_confirmations_requested_total", action="register_for_event") == before + 1


def test_language_model_requests_are_counted_by_outcome_and_tokens_when_reported(monkeypatch):
    from types import SimpleNamespace

    from fakes import RaisingGroq, _chunks
    import groq
    import httpx

    class WithUsage(FakeGroq):
        def _create(self, **kwargs):
            chunks = list(_chunks(self._replies[0]))
            chunks.insert(-1, SimpleNamespace(choices=[], usage=SimpleNamespace(prompt_tokens=11, completion_tokens=5)))
            return iter(chunks)

    labels = dict(provider="groq", model="balanced-model")
    before_ok = sample("llm_requests_total", tier="balanced", outcome="ok", **labels)
    before_tokens = (sample("llm_tokens_used_total", kind="prompt", **labels), sample("llm_tokens_used_total", kind="completion", **labels))
    fake_llm(WithUsage(_completion(content="hi"))).chat_completion([{"role": "user", "content": "x"}])
    assert sample("llm_requests_total", tier="balanced", outcome="ok", **labels) == before_ok + 1
    assert sample("llm_tokens_used_total", kind="prompt", **labels) == before_tokens[0] + 11
    assert sample("llm_tokens_used_total", kind="completion", **labels) == before_tokens[1] + 5

    before_err = sample("llm_requests_total", tier="balanced", outcome="error", **labels)
    with pytest.raises(AppError):
        fake_llm(RaisingGroq(groq.APIConnectionError(request=httpx.Request("POST", "http://x")))).chat_completion([])
    assert sample("llm_requests_total", tier="balanced", outcome="error", **labels) == before_err + 1
    assert sample("llm_request_duration_seconds_count", provider="groq", model="balanced-model") >= 2


# --- tracing


@pytest.fixture
def traced(db):
    from app.db import session as db_session

    exporter = InMemorySpanExporter()
    traced_app = FastAPI()

    @traced_app.get("/ping/{item}")
    def ping(item: str):
        with db_session.SessionLocal() as session:
            session.execute(text("select 1"))
        get_logger("traced").info("inside.request")
        return {"item": item}

    provider = setup_tracing(traced_app, db_session.SessionLocal.kw["bind"], exporter=exporter)
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    yield TestClient(traced_app), exporter
    from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

    SQLAlchemyInstrumentor().uninstrument()


def test_a_request_and_its_database_queries_become_spans_of_one_trace(traced):
    client, exporter = traced
    client.get("/ping/abc")
    provider_spans = exporter.get_finished_spans()
    names = {s.name for s in provider_spans}
    assert any(n.startswith("GET /ping") for n in names) and any("select" in n.lower() or n == "connect" for n in names)
    assert len({s.context.trace_id for s in provider_spans}) == 1


def test_log_lines_carry_the_trace_id_of_the_request(traced, logs):
    client, exporter = traced
    client.get("/ping/abc")
    inside = [l for l in logs() if l["event"] == "inside.request"][0]
    server_span = next(s for s in exporter.get_finished_spans() if s.name.startswith("GET /ping"))
    assert inside["trace_id"] == format(server_span.context.trace_id, "032x")


def test_without_a_collector_nothing_is_traced(db, monkeypatch):
    from app.db import session as db_session

    monkeypatch.setattr(config, "OTEL_EXPORTER_OTLP_ENDPOINT", "")
    assert setup_tracing(FastAPI(), db_session.SessionLocal.kw["bind"]) is None


# --- Sentry


class Capture:
    """A Sentry transport that keeps what would have been sent."""

    def __init__(self):
        self.events = []

    def make(self):
        from sentry_sdk.transport import Transport

        outer = self

        class Keeper(Transport):
            def capture_envelope(self, envelope):
                for item in envelope.items:
                    if item.type == "event":
                        outer.events.append(item.payload.json)

        return Keeper()


@pytest.fixture
def sentry():
    import sentry_sdk

    capture = Capture()
    assert init_sentry(dsn="https://public@o0.ingest.sentry.io/1", transport=capture.make()) is True
    yield capture
    sentry_sdk.get_client().close()
    sentry_sdk.init()  # disabled again


def sentry_app():
    broken = FastAPI()
    register_error_handlers(broken)

    @broken.get("/boom")
    def boom():
        raise RuntimeError("kaboom")

    @broken.get("/expected")
    def expected():
        raise AppError(409, "conflict", "expected failure")

    return TestClient(broken, raise_server_exceptions=False)


def test_unexpected_errors_are_reported_and_expected_ones_are_not(sentry):
    client = sentry_app()
    client.get("/expected")
    client.get("/boom")
    import sentry_sdk

    sentry_sdk.flush()
    kinds = [e["exception"]["values"][0]["type"] for e in sentry.events if "exception" in e]
    assert kinds == ["RuntimeError"]


def test_nothing_personal_is_sent_with_an_error(sentry):
    client = sentry_app()
    client.cookies.set("access_token", "super-secret-token")
    client.get("/boom?email=a@b.c", headers={"Authorization": "Bearer another-secret"})
    import sentry_sdk

    sentry_sdk.flush()
    sent = json.dumps(sentry.events)
    assert sentry.events and "super-secret-token" not in sent and "another-secret" not in sent and "a@b.c" not in sent


def test_without_a_dsn_sentry_stays_off(monkeypatch):
    monkeypatch.setattr(config, "SENTRY_DSN", "")
    assert init_sentry() is False


def test_a_slow_stream_is_timed_to_its_last_chunk_not_its_first(logs):
    import asyncio

    async def streaming(scope, receive, send):
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"one", "more_body": True})
        await asyncio.sleep(0.15)
        await send({"type": "http.response.body", "body": b"two", "more_body": False})

    wrapped = RequestLoggingMiddleware(streaming)
    sent = []

    async def go():
        async def send(message):
            sent.append(message)

        async def receive():
            return {"type": "http.disconnect"}

        await wrapped({"type": "http", "method": "GET", "path": "/slow", "headers": []}, receive, send)

    asyncio.run(go())
    (line,) = request_lines(logs)
    assert line["duration_ms"] >= 140 and line["status"] == 200
    assert any(h[0] == b"x-request-id" for h in sent[0]["headers"])
