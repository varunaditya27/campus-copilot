from typing import Annotated

from pydantic import Field, validate_call


@validate_call
def calculate_attendance(attended: Annotated[int, Field(ge=0)], total: int) -> dict:
    """The LLM decides *when* to call this; Python does the actual math.
    Never trust a language model with arithmetic it can just compute wrong."""
    if total <= 0:
        return {"error": "Total classes must be greater than zero"}
    if attended > total:
        return {"error": "Classes attended cannot exceed total classes"}
    return {"percentage": round((attended / total) * 100, 2)}
