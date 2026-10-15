from app.llm.base import QUALITY_TIERS


def tier_for(requested: str | None, agentic: bool) -> str:
    """The quality tier for a model call.

    A tier the student asked for is used as asked. Otherwise ordinary questions get
    "balanced", and a multi-step agentic task (a plan, or tools already used and their
    results being worked through) gets "best"."""
    if requested in QUALITY_TIERS:
        return requested
    return "best" if agentic else "balanced"
