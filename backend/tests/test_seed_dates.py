from datetime import date, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import clock
from app.db import session as db_session
from app.db.models import Base, BookLoan, CounsellingSlot, Event, Exam, PlacementDrive, Registration
from app.db.seed import seed

SAMPLE_DAY = date(2026, 10, 15)  # the day the files in data/ were written for


@pytest.fixture
def load(tmp_path, monkeypatch):
    """Seed an empty database as if on the given day, and return its engine."""

    def on(day: date):
        engine = db_session.make_engine(f"sqlite:///{tmp_path / 'seed.db'}")
        Base.metadata.create_all(engine)
        monkeypatch.setattr(clock, "today", lambda: day)
        with Session(engine) as session:
            seed(session)
        return engine

    return on


def column(engine, values):
    with Session(engine) as session:
        return sorted(session.scalars(select(values)))


def test_on_the_sample_day_the_dates_are_those_in_the_files(load):
    engine = load(SAMPLE_DAY)
    assert column(engine, CounsellingSlot.date)[0] == "2026-10-16"
    assert column(engine, Exam.date)[0] == "2026-09-07"


def test_a_later_load_day_moves_every_date_by_the_same_number_of_days(load):
    engine = load(date(2026, 11, 10))  # 26 days after the sample day

    slots = column(engine, CounsellingSlot.date)
    assert (slots[0], slots[-1]) == ("2026-11-11", "2026-12-01")
    assert column(engine, BookLoan.borrowed_on)[-1] == "2026-11-10"  # the newest loan is from the load day
    assert column(engine, PlacementDrive.date)[0] == "2026-11-22"
    assert column(engine, Exam.date)[0] == "2026-10-03"


def test_the_events_start_tomorrow_whatever_the_load_day(load):
    engine = load(date(2027, 3, 5))

    events = column(engine, Event.date)
    assert events[0] == "2027-03-06"
    assert (date.fromisoformat(events[-1]) - date.fromisoformat(events[0])).days == 30  # the spacing is kept


def test_registrations_stay_just_before_their_events(load):
    engine = load(date(2027, 3, 5))
    with Session(engine) as session:
        rows = session.execute(select(Registration.registered_at, Event.date).join(Event, Event.id == Registration.event_id)).all()

    assert rows and all(registered_at.date() < date.fromisoformat(event_date) for registered_at, event_date in rows)
    assert all(registered_at <= datetime(2027, 3, 6) for registered_at, _ in rows)


def test_loading_again_on_a_later_day_does_not_move_anything_twice(load):
    engine = load(date(2026, 11, 10))
    before = column(engine, CounsellingSlot.date), column(engine, Event.date)

    with Session(engine) as session:
        seed(session)  # the tables are full, so nothing is loaded or moved

    assert (column(engine, CounsellingSlot.date), column(engine, Event.date)) == before
