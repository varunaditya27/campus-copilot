def calculate_attendance(attended: int, total: int) -> dict:
    """The LLM decides *when* to call this; Python does the actual math.
    Never trust a language model with arithmetic it can just compute wrong."""
    if total <= 0:
        return {"error": "Total classes must be greater than zero"}
    return {"percentage": round((attended / total) * 100, 2)}
