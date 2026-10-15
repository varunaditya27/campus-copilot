from datetime import date


def today() -> date:
    """Today's date. Services call this instead of date.today() so tests can set the day."""
    return date.today()
