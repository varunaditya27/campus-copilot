from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from icalendar import Calendar

from app.db.models import Event
from app.main import app
from helpers import ADMIN, ASHA, ASHA_PROFILE, RAVI_PROFILE, register_through_approval, sign_in_as, sign_up

URL = "/api/students/me/calendar.ics"


@pytest.fixture
def asha(db):
    return sign_up(TestClient(app), ASHA)


def entries(response):
    return list(Calendar.from_ical(response.content).walk("VEVENT"))


def test_a_student_downloads_their_registered_events_as_a_calendar_file(asha):
    register_through_approval(ASHA_PROFILE)
    response = asha.get(URL)

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/calendar")
    assert "attachment" in response.headers["content-disposition"]
    (entry,) = entries(response)
    assert str(entry["summary"]) == "AI Workshop" and str(entry["location"]) == "Hall A"
    assert entry["dtstart"].dt == datetime(2026, 9, 1, 10, 0, tzinfo=ZoneInfo("Asia/Kolkata"))
    assert entry["dtend"].dt - entry["dtstart"].dt == timedelta(minutes=60)


def test_the_file_holds_only_the_students_own_events_and_is_valid_when_empty(asha):
    register_through_approval(RAVI_PROFILE)
    response = asha.get(URL)

    assert response.status_code == 200 and entries(response) == []
    assert response.content.startswith(b"BEGIN:VCALENDAR") and b"VERSION:2.0" in response.content


def test_commas_semicolons_and_long_text_survive_the_trip(db, asha):
    register_through_approval(ASHA_PROFILE)
    with db.begin() as session:
        event = session.get(Event, "evt_ai_001")
        event.name = r"Robots, AI; and a back\slash"
        event.description = "First line\nSecond line " + "word " * 60
    response = asha.get(URL)

    (entry,) = entries(response)
    assert str(entry["summary"]) == r"Robots, AI; and a back\slash"
    assert str(entry["description"]).startswith("First line\nSecond line word")
    lines = response.content.split(b"\r\n")
    assert all(len(line) <= 75 for line in lines) and b"\n" not in b"".join(lines)


def test_an_event_keeps_the_same_id_each_time_so_a_calendar_app_does_not_duplicate_it(asha):
    register_through_approval(ASHA_PROFILE)
    first, second = entries(asha.get(URL)), entries(asha.get(URL))
    assert str(first[0]["uid"]) == str(second[0]["uid"])


def test_only_a_signed_in_student_can_download_one(db):
    assert TestClient(app).get(URL).status_code == 401
    assert sign_in_as(ADMIN).get(URL).status_code == 403
