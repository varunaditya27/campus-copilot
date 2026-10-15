import groq
import openai

from app.core import config
from app.llm.openai_compatible import OpenAICompatibleClient

# Groq's production chat models as of its models page in October 2026. llama-3.1-8b-instant and
# llama-3.3-70b-versatile were scheduled to shut down for free and developer accounts on 2026-08-16.
GROQ_FAST_MODEL = "openai/gpt-oss-20b"
GROQ_BALANCED_MODEL = "openai/gpt-oss-120b"
# No larger production model exists on Groq, so "best" is the same model as "balanced" unless set.


class LLMConfigError(RuntimeError):
    """The chosen provider is not configured well enough to use."""


def _models(provider: str, defaults: dict[str, str]) -> dict[str, str]:
    balanced = config.LLM_MODEL or defaults.get("balanced", "")
    if not balanced:
        raise LLMConfigError(f"LLM_MODEL is required when LLM_PROVIDER={provider}: name a model that supports tool calls.")
    return {
        "fast": config.LLM_MODEL_FAST or defaults.get("fast") or balanced,
        "balanced": balanced,
        "best": config.LLM_MODEL_BEST or defaults.get("best") or balanced,
    }


def _key(value: str, name: str) -> str:
    if not value:
        raise LLMConfigError(f"{name} is not set.")
    return value


class GroqLLMClient(OpenAICompatibleClient):
    def __init__(self, raw=None, models: dict[str, str] | None = None) -> None:
        models = models or _models("groq", {"fast": GROQ_FAST_MODEL, "balanced": config.GROQ_MODEL or GROQ_BALANCED_MODEL})
        super().__init__("groq", raw or groq.Groq(api_key=_key(config.GROQ_API_KEY, "GROQ_API_KEY")), groq, models)


class OpenAILLMClient(OpenAICompatibleClient):
    def __init__(self, raw=None, models: dict[str, str] | None = None) -> None:
        models = models or _models("openai", {})
        if raw is None:
            # A server of your own that speaks the protocol may not need a key, but the SDK insists on one.
            key = config.OPENAI_API_KEY or ("unused" if config.OPENAI_BASE_URL else _key("", "OPENAI_API_KEY"))
            raw = openai.OpenAI(api_key=key, base_url=config.OPENAI_BASE_URL or None)
        super().__init__("openai", raw, openai, models, stream_usage=True)


class OllamaLLMClient(OpenAICompatibleClient):
    """A model running on this machine, through Ollama's OpenAI-compatible endpoint. No API cost, works offline."""

    def __init__(self, raw=None, models: dict[str, str] | None = None) -> None:
        models = models or _models("ollama", {})
        # The key is required by the SDK and ignored by Ollama.
        raw = raw or openai.OpenAI(api_key="ollama", base_url=config.OLLAMA_BASE_URL)
        super().__init__("ollama", raw, openai, models, stream_usage=True)


PROVIDERS = {"groq": GroqLLMClient, "openai": OpenAILLMClient, "ollama": OllamaLLMClient}

