from datetime import date, datetime


def today() -> date:
    """Today's date. Services call this instead of date.today() so tests can set the day."""
    return date.today()


def now() -> datetime:
    """The current local time, for the same reason as today()."""
    return datetime.now()
