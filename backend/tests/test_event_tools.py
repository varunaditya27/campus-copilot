from app.tools.events import check_event_availability, search_events


def test_search_matches_keyword(db):
    results = search_events("workshop")
    assert [e["id"] for e in results] == ["evt_ai_001"]


def test_search_is_case_insensitive(db):
    assert [e["id"] for e in search_events("REACT")] == ["evt_web_002"]


def test_search_ignores_words_of_two_letters_or_fewer(db):
    # "ai" is dropped, so no search words remain and every event matches.
    assert len(search_events("ai")) == 2


def test_search_with_no_match_returns_empty_list(db):
    assert search_events("quantum") == []


def test_availability_with_free_seats(db):
    assert check_event_availability("evt_ai_001") == {
        "available": True,
        "remaining_seats": 6,
    }


def test_availability_when_full(db):
    assert check_event_availability("evt_web_002") == {
        "available": False,
        "remaining_seats": 0,
    }


def test_availability_unknown_event(db):
    assert "error" in check_event_availability("nope")
