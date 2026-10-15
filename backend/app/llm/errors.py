from types import ModuleType

from app.core.errors import AppError

# Groq documents 413 for an oversized request but no specific code for an
# over-long prompt, so a 400 is matched by its message wording as well.
_CONTEXT_TOO_LONG_HINTS = ("context length", "reduce the length", "too long", "maximum context")


def to_app_error(exc: Exception, sdk: ModuleType) -> AppError:
    """Turn a provider SDK's exception into the application's own error."""
    if isinstance(exc, sdk.RateLimitError):
        return AppError(429, "rate_limited", "The AI service is busy right now. Please try again in a moment.")
    too_long = (isinstance(exc, sdk.APIStatusError) and exc.status_code == 413) or (
        isinstance(exc, sdk.BadRequestError) and any(hint in exc.message.lower() for hint in _CONTEXT_TOO_LONG_HINTS)
    )
    if too_long:
        return AppError(413, "context_too_long", "This conversation is too long. Please start a new chat.")
    return AppError(502, "llm_unavailable", "The AI service is unavailable right now. Please try again shortly.")
