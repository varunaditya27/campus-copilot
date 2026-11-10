import time
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from app.core import clock


@pytest.fixture
def server_in_los_angeles(monkeypatch):
    """A server whose own clock is set to a zone far from the campus."""
    monkeypatch.setenv("TZ", "America/Los_Angeles")
    time.tzset()
    yield
    monkeypatch.undo()
    time.tzset()


def test_the_time_is_campus_time_whatever_zone_the_server_runs_in(server_in_los_angeles):
    campus = datetime.now(ZoneInfo("Asia/Kolkata")).replace(tzinfo=None)

    assert abs((clock.now() - campus).total_seconds()) < 5
    assert abs((datetime.now() - campus).total_seconds()) > 3600  # the server's own clock really is elsewhere
    assert clock.now().tzinfo is None  # event dates and times are stored without a zone


def test_today_follows_the_campus_date(monkeypatch):
    class Fixed(datetime):
        @classmethod
        def now(cls, tz=None):
            # 20:00 on 9 March in Los Angeles is already 10 March in India.
            return datetime(2026, 3, 9, 20, 0, tzinfo=ZoneInfo("America/Los_Angeles")).astimezone(tz)

    monkeypatch.setattr(clock, "datetime", Fixed)
    assert clock.today().isoformat() == "2026-03-10"
