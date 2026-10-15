from abc import ABC, abstractmethod
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass, field

QUALITY_TIERS = ("fast", "balanced", "best")


@dataclass(frozen=True)
class Usage:
    prompt_tokens: int
    completion_tokens: int


@dataclass(frozen=True)
class ToolCallPart:
    """A fragment of a tool call: an id and name come first, then the JSON arguments in pieces."""

    index: int
    id: str | None = None
    name: str | None = None
    arguments: str | None = None


@dataclass(frozen=True)
class LLMChunk:
    text: str = ""
    tool_call_parts: tuple[ToolCallPart, ...] = ()
    usage: Usage | None = None


@dataclass
class Completion:
    text: str
    tool_calls: list[dict] = field(default_factory=list)  # {"id", "name", "arguments"} with the arguments as a JSON string
    usage: Usage | None = None


def collect(chunks: Iterable[LLMChunk], on_text: Callable[[str], None] | None = None) -> Completion:
    """Put a stream back together: the text, and the tool calls reassembled from their fragments by index."""
    text_parts: list[str] = []
    calls: dict[int, dict] = {}
    usage = None
    for chunk in chunks:
        if chunk.text:
            text_parts.append(chunk.text)
            if on_text:
                on_text(chunk.text)
        for part in chunk.tool_call_parts:
            call = calls.setdefault(part.index, {"id": None, "name": "", "arguments": ""})
            if part.id:
                call["id"] = part.id
            if part.name:
                call["name"] = part.name
            if part.arguments:
                call["arguments"] += part.arguments
        if chunk.usage:
            usage = chunk.usage
    tool_calls = [{**calls[i], "id": calls[i]["id"] or f"call_{i}"} for i in sorted(calls)]
    return Completion(text="".join(text_parts), tool_calls=tool_calls, usage=usage)


class BaseLLMClient(ABC):
    """What the agent needs from a language model, whichever service or program provides it.

    A provider implements stream_completion; the other two are built on it. Failures
    are raised as AppError, so the rest of the application never sees a provider's own exceptions."""

    provider: str

    @abstractmethod
    def model_for(self, tier: str) -> str:
        """The model used for a quality tier (fast, balanced or best)."""

    @abstractmethod
    def stream_completion(
        self, messages: list[dict], tools: list[dict] | None = None, tier: str = "balanced"
    ) -> Iterator[LLMChunk]:
        """Stream one model round as chunks of text and tool-call fragments."""

    def chat_completion(
        self, messages: list[dict], tools: list[dict] | None = None, tier: str = "balanced"
    ) -> Completion:
        """One complete model round, waiting for the whole answer."""
        return collect(self.stream_completion(messages, tools, tier))

    def tool_call(self, messages: list[dict], tools: list[dict], tier: str = "balanced") -> list[dict]:
        """Ask the model which tools to call: the tool calls of one round, empty if it answered in text."""
        return self.chat_completion(messages, tools, tier).tool_calls
