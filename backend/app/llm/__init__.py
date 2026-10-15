from functools import lru_cache

from app.core import config
from app.llm.base import BaseLLMClient
from app.llm.providers import PROVIDERS, LLMConfigError


@lru_cache
def get_llm_client() -> BaseLLMClient:
    """The language-model client for the configured provider (LLM_PROVIDER)."""
    try:
        return PROVIDERS[config.LLM_PROVIDER]()
    except KeyError:
        raise LLMConfigError(f"LLM_PROVIDER must be one of {', '.join(PROVIDERS)}, not '{config.LLM_PROVIDER}'.") from None


__all__ = ["BaseLLMClient", "LLMConfigError", "get_llm_client"]
