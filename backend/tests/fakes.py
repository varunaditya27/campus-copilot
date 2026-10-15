"""Fakes: Groq clients that stream chunks like the real SDK, and a model-free embedding."""
import hashlib
import json
import math
from types import SimpleNamespace

from app.rag.embeddings import BaseEmbeddingFunction


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


class FakeEmbedding(BaseEmbeddingFunction):
    """Bag-of-hashed-words vectors: texts that share words end up close together.
    Deterministic and instant, so tests can use a real Chroma without the model."""

    identity = "fake-embedding"

    def __init__(self):
        pass

    def embed(self, texts):
        vectors = []
        for text in texts:
            vector = [0.0] * 64
            for word in text.lower().split():
                vector[int(hashlib.md5(word.encode()).hexdigest(), 16) % 64] += 1.0
            norm = math.sqrt(sum(x * x for x in vector)) or 1.0
            vectors.append([x / norm for x in vector])
        return vectors

    @staticmethod
    def name():
        return "fake-embedding"

    def get_config(self):
        return {}

    @staticmethod
    def build_from_config(config):
        return FakeEmbedding()


def make_pdf(pages: list[str]) -> bytes:
    """A minimal valid PDF with one line of text per page (an empty string gives a
    blank page with no text)."""

    def escape(text):
        return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    kids = " ".join(f"{4 + 2 * i} 0 R" for i in range(len(pages)))
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        f"<< /Type /Pages /Kids [{kids}] /Count {len(pages)} >>".encode(),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    for i, text in enumerate(pages):
        objects.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents {5 + 2 * i} 0 R "
            f"/Resources << /Font << /F1 3 0 R >> >> >>".encode()
        )
        stream = f"BT /F1 12 Tf 72 720 Td ({escape(text)}) Tj ET".encode() if text else b""
        objects.append(b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream")

    out = b"%PDF-1.4\n"
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n".encode() + body + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    out += b"".join(f"{offset:010d} 00000 n \n".encode() for offset in offsets)
    out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return out


class SlowGroq:
    """Streams a text reply one word at a time with a pause between words, and records
    when the stream finished."""

    def __init__(self, words, pause=0.05):
        self._words, self._pause = words, pause
        self.finished_at = None
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        import time

        def stream():
            for word in self._words:
                time.sleep(self._pause)
                yield _chunk(content=word + " ")
            yield _chunk(finish_reason="stop")
            self.finished_at = time.monotonic()

        return stream()


def fake_llm(raw, models=None):
    """Wrap a fake SDK client (anything with chat.completions.create) as the application's LLM client,
    so provider error mapping runs just as it does for the real one."""
    from app.llm.providers import GroqLLMClient

    return GroqLLMClient(raw, models or {"fast": "fast-model", "balanced": "balanced-model", "best": "best-model"})
