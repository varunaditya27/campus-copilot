from datetime import date, datetime
from zoneinfo import ZoneInfo

# Event dates and times are stored without a zone: they are campus local time, whatever zone the server runs in.
CAMPUS_TIMEZONE = ZoneInfo("Asia/Kolkata")


def today() -> date:
    """Today's date on campus. Services call this instead of date.today() so tests can set the day."""
    return datetime.now(CAMPUS_TIMEZONE).date()


def now() -> datetime:
    """The current campus time, without a zone to match the stored event times, for the same reason as today()."""
    return datetime.now(CAMPUS_TIMEZONE).replace(tzinfo=None)
