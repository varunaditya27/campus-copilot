"""Fake Groq clients that emit streamed chunks the way the real SDK does."""
import json
from types import SimpleNamespace


def tool_call(call_id, name, args):
    return SimpleNamespace(
        id=call_id,
        function=SimpleNamespace(name=name, arguments=json.dumps(args)),
    )


def completion(content=None, tool_calls=None):
    """One scripted model reply: optional text and optional tool calls."""
    return SimpleNamespace(content=content, tool_calls=tool_calls)


def _chunk(content=None, tool_calls=None, finish_reason=None):
    delta = SimpleNamespace(content=content, tool_calls=tool_calls)
    return SimpleNamespace(choices=[SimpleNamespace(delta=delta, finish_reason=finish_reason)])


def _chunks(reply):
    """Split a scripted reply into chunks. Text and each tool call's JSON
    arguments are cut in two, so the code under test must reassemble them."""
    if reply.content:
        mid = max(1, len(reply.content) // 2)
        yield _chunk(content=reply.content[:mid])
        yield _chunk(content=reply.content[mid:])
    for index, call in enumerate(reply.tool_calls or []):
        arguments = call.function.arguments
        mid = len(arguments) // 2
        yield _chunk(
            tool_calls=[
                SimpleNamespace(
                    index=index,
                    id=call.id,
                    function=SimpleNamespace(name=call.function.name, arguments=arguments[:mid]),
                )
            ]
        )
        yield _chunk(
            tool_calls=[
                SimpleNamespace(
                    index=index,
                    id=None,
                    function=SimpleNamespace(name=None, arguments=arguments[mid:]),
                )
            ]
        )
    yield _chunk(finish_reason="tool_calls" if reply.tool_calls else "stop")
    # The real API can end a stream with a chunk that has no choices (usage info).
    yield SimpleNamespace(choices=[])


class FakeGroq:
    """Returns the scripted replies in order; repeats the last one forever."""

    def __init__(self, *replies):
        self._replies = list(replies)
        self.calls = 0
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        index = min(self.calls, len(self._replies) - 1)
        self.calls += 1
        return _chunks(self._replies[index])


class RaisingGroq:
    """Fails as soon as the request is made (for example a 429)."""

    def __init__(self, exc):
        self._exc = exc
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        raise self._exc


class FailingStreamGroq:
    """Starts streaming some text, then the connection fails."""

    def __init__(self, exc):
        self._exc = exc
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        def stream():
            yield _chunk(content="partial ")
            raise self._exc

        return stream()
