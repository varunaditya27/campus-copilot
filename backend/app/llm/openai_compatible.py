from collections.abc import Iterator
from types import ModuleType

from app.llm.base import BaseLLMClient, LLMChunk, ToolCallPart, Usage
from app.llm.errors import to_app_error


def _usage_of(chunk) -> Usage | None:
    # OpenAI and Ollama put it on the last chunk. Groq's streaming usage is not documented,
    # so look in both places it might be and take it only if it is there.
    usage = getattr(chunk, "usage", None) or getattr(getattr(chunk, "x_groq", None), "usage", None)
    if usage is None:
        return None
    prompt, completion = getattr(usage, "prompt_tokens", None), getattr(usage, "completion_tokens", None)
    return Usage(prompt, completion) if isinstance(prompt, int) and isinstance(completion, int) else None


class OpenAICompatibleClient(BaseLLMClient):
    """A client for any service that speaks the OpenAI chat-completions protocol, through its SDK.

    Groq, OpenAI and Ollama all do, so they share this code and differ only in the SDK
    object, the models, and whether the service can report token usage while streaming."""

    def __init__(
        self,
        provider: str,
        raw,
        sdk: ModuleType,
        models: dict[str, str],
        stream_usage: bool = False,
    ) -> None:
        self.provider = provider
        self._raw = raw  # the SDK client: raw.chat.completions.create(...)
        self._sdk = sdk
        self._models = models
        self._stream_usage = stream_usage

    def model_for(self, tier: str) -> str:
        return self._models[tier]

    def stream_completion(
        self, messages: list[dict], tools: list[dict] | None = None, tier: str = "balanced"
    ) -> Iterator[LLMChunk]:
        options: dict = {}
        if tools:
            options["tools"] = tools  # tool_choice is left at its default, "auto"; some servers reject the field
        if self._stream_usage:
            options["stream_options"] = {"include_usage": True}
        try:
            stream = self._raw.chat.completions.create(
                model=self.model_for(tier), messages=messages, stream=True, **options
            )
            for chunk in stream:
                usage = _usage_of(chunk)
                if not chunk.choices:
                    if usage:
                        yield LLMChunk(usage=usage)
                    continue
                delta = chunk.choices[0].delta
                parts = tuple(
                    ToolCallPart(
                        index=part.index,
                        id=part.id,
                        name=part.function.name if part.function else None,
                        arguments=part.function.arguments if part.function else None,
                    )
                    for part in delta.tool_calls or []
                )
                yield LLMChunk(text=delta.content or "", tool_call_parts=parts, usage=usage)
        except self._sdk.APIError as exc:
            raise to_app_error(exc, self._sdk) from exc
