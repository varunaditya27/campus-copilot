import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime
from uuid import UUID

import pytest
from sqlalchemy import select

from app.actions.base import ActionError
from app.core import clock
from app.db.models import (
    BookReservation,
    CounsellingSlot,
    GrievanceTicket,
    LostFoundItem,
    MaintenanceRequest,
    RoomBooking,
)
from app.services import (
    action_service,
    campus_service,
    library_service,
    placement_service,
    study_room_service,
    support_service,
)
from helpers import ASHA_PROFILE, RAVI_PROFILE, add_academic_data, add_operations_data, add_schedule_data

ASHA = "1RV23IS101"
RAVI = "1RV24IS219"
ARJUN = "1RV22CS220"
ARJUN_PROFILE = RAVI_PROFILE.model_copy(update={"user_id": 3, "student_id": ARJUN, "name": "Arjun", "year": 4})
MONDAY_MORNING = datetime(2026, 10, 19, 10, 10)


@pytest.fixture
def data(db):
    add_operations_data(db)


@pytest.fixture
def set_now(monkeypatch):
    def setter(moment):
        monkeypatch.setattr(clock, "now", lambda: moment)
        monkeypatch.setattr(clock, "today", lambda: moment.date())

    setter(MONDAY_MORNING)
    return setter


def run(student, name, **args):
    """Propose an action and approve it, the way the application does."""
    confirmation = action_service.propose(student, name, args)
    return action_service.confirm(UUID(confirmation.action_id), student)


def refused(student, name, **args):
    with pytest.raises(ActionError) as info:
        action_service.propose(student, name, args)
    return str(info.value)


# --- library


def test_a_copy_on_the_shelf_is_available_with_its_location(data):
    (book,) = library_service.availability("sedgewick")["books"]
    assert (book["status"], book["copies_available"], book["shelf_location"]) == ("available", 2, "First floor, shelf CO-01")


def test_when_every_copy_is_out_the_earliest_return_and_the_queue_are_shown(data):
    (book,) = library_service.availability("introduction to algorithms")["books"]
    assert (book["status"], book["copies_available"], book["earliest_due_back"], book["holds_waiting"]) == ("all_out", 0, "2026-10-20", 1)


def test_some_copies_out_still_means_available(data):
    (book,) = library_service.availability("operating system")["books"]
    assert (book["copies_available"], book["status"]) == (2, "available")


def test_reference_books_do_not_circulate(data):
    (book,) = library_service.availability("encyclopedia")["books"]
    assert book["status"] == "reference_only" and "do not circulate" in book["note"] and "copies_available" not in book


def test_every_word_must_match_in_any_of_title_author_or_isbn(data):
    assert [b["book_id"] for b in library_service.availability("algorithms cormen")["books"]] == ["BK-1"]
    assert [b["book_id"] for b in library_service.availability("demo-bk-4")["books"]] == ["BK-4"]
    assert "error" in library_service.availability("algorithms nobody")


def test_a_broad_search_is_capped(db):
    from app.db.models import Book

    with db.begin() as session:
        session.add_all(
            Book(book_id=f"B{i}", title=f"Physics {i}", author="X", isbn=f"I{i}", category="c", shelf_location="s", copies_total=1)
            for i in range(8)
        )
    result = library_service.availability("physics")
    assert len(result["books"]) == library_service.MAX_RESULTS and result["more_matches"] == 3


@pytest.mark.parametrize("query", ["%", "_", "   "])
def test_wildcards_and_blanks_find_nothing(data, query):
    assert "error" in library_service.availability(query)


def test_reserving_a_book_with_no_copy_joins_the_queue(data, set_now):
    outcome = run(ASHA_PROFILE, "reserve_library_book", book_id="BK-1")
    assert (outcome.success, outcome.details) == (True, {"Queue place": "2"})


def test_the_preview_shows_the_wait(data, set_now):
    confirmation = action_service.propose(ASHA_PROFILE, "reserve_library_book", {"book_id": "bk-1"})
    lines = {line.label: line.value for line in confirmation.lines}
    assert lines["Due back"] == "2026-10-20" and lines["Your place"] == "2"


@pytest.mark.parametrize(
    "who, book, reason",
    [
        (ASHA_PROFILE, "BK-4", "on the shelf"),
        (ASHA_PROFILE, "BK-2", "on the shelf"),
        (ASHA_PROFILE, "BK-3", "reference book"),
        (ASHA_PROFILE, "BK-99", "couldn't find"),
        (RAVI_PROFILE, "BK-1", "already have a copy"),
        (ARJUN_PROFILE, "BK-1", "already have"),
    ],
)
def test_reservations_that_make_no_sense_are_refused_early(data, set_now, who, book, reason):
    assert reason in refused(who, "reserve_library_book", book_id=book)


def test_a_hold_cannot_be_placed_twice(data, set_now):
    run(ASHA_PROFILE, "reserve_library_book", book_id="BK-1")
    assert "already have a hold" in refused(ASHA_PROFILE, "reserve_library_book", book_id="BK-1")


def test_a_hold_is_refused_if_a_copy_came_back_while_waiting(data, set_now, db):
    from app.db.models import BookLoan

    confirmation = action_service.propose(ASHA_PROFILE, "reserve_library_book", {"book_id": "BK-1"})
    with db.begin() as session:
        session.delete(session.scalar(select(BookLoan).where(BookLoan.book_id == "BK-1")))
    outcome = action_service.confirm(UUID(confirmation.action_id), ASHA_PROFILE)
    assert outcome.success is False and "on the shelf" in outcome.message
    with db() as session:
        assert session.scalar(select(BookReservation).where(BookReservation.student_id == ASHA)) is None


# --- study rooms


def test_every_room_lists_its_free_blocks_for_a_weekday(data, set_now):
    result = study_room_service.availability("2026-10-20")
    assert result["weekday"] == "Tuesday"
    assert result["rooms"][0] == {
        "room_id": "DR-1", "name": "Discussion Room 1", "capacity": 4,
        "free_slots": ["08:00-10:00", "10:00-12:00", "12:00-14:00", "14:00-16:00", "16:00-18:00", "18:00-20:00"],
    }


def test_blocks_that_have_started_today_are_not_offered(data, set_now):
    slots = study_room_service.availability("today")["rooms"][0]["free_slots"]
    assert slots == ["12:00-14:00", "14:00-16:00", "16:00-18:00", "18:00-20:00"]


def test_saturday_has_shorter_hours_and_sunday_is_closed(data, set_now):
    set_now(datetime(2026, 10, 23, 9, 0))
    saturday = study_room_service.availability("2026-10-24")["rooms"][0]["free_slots"]
    assert saturday == ["09:00-11:00", "11:00-13:00", "13:00-15:00", "15:00-17:00"]
    assert "closed on Sundays" in study_room_service.availability("2026-10-25")["error"]


def test_a_room_can_be_filtered_by_group_size(data, set_now):
    assert [r["room_id"] for r in study_room_service.availability("tomorrow", min_capacity=6)["rooms"]] == ["DR-7"]


@pytest.mark.parametrize("day, message", [("2026-10-18", "passed"), ("2026-10-23", "3 days ahead"), ("soon", "not a date")])
def test_dates_outside_the_booking_window_are_errors(data, set_now, day, message):
    assert message in study_room_service.availability(day)["error"]


def test_booking_a_room_makes_it_unavailable(data, set_now, db):
    outcome = run(ASHA_PROFILE, "book_study_room", room_id="dr-7", date="tomorrow", time_slot="14:00-16:00")
    assert outcome.success and "2026-10-20 from 14:00 to 16:00" in outcome.message
    assert "14:00-16:00" not in study_room_service.availability("2026-10-20")["rooms"][1]["free_slots"]
    with db() as session:
        row = session.scalar(select(RoomBooking))
        assert (row.student_id, row.room_id, row.start, row.end) == (ASHA, "DR-7", "14:00", "16:00")


def test_a_taken_slot_is_refused_for_the_next_student(data, set_now):
    run(ASHA_PROFILE, "book_study_room", room_id="DR-1", date="2026-10-20", time_slot="10:00")
    assert "already booked" in refused(RAVI_PROFILE, "book_study_room", room_id="DR-1", date="2026-10-20", time_slot="10:00")


@pytest.mark.parametrize(
    "args, reason",
    [
        ({"room_id": "DR-1", "date": "2026-10-20", "time_slot": "11:00"}, "two-hour blocks"),
        ({"room_id": "DR-1", "date": "2026-10-19", "time_slot": "08:00"}, "already started"),
        ({"room_id": "DR-9", "date": "2026-10-20", "time_slot": "10:00"}, "couldn't find that room"),
        ({"room_id": "DR-1", "date": "2026-10-30", "time_slot": "10:00"}, "3 days ahead"),
        ({"room_id": "DR-1", "date": "2026-10-20"}, "time slot"),
        ({"room_id": 4, "date": "2026-10-20", "time_slot": "10:00"}, "room id"),
    ],
)
def test_impossible_bookings_are_refused_with_the_reason(data, set_now, args, reason):
    assert reason in refused(ASHA_PROFILE, "book_study_room", **args)


def test_two_students_racing_for_one_slot_get_one_booking(data, set_now, db):
    confirmations = [
        (p, action_service.propose(p, "book_study_room", {"room_id": "DR-1", "date": "2026-10-20", "time_slot": "10:00"}))
        for p in (ASHA_PROFILE, RAVI_PROFILE)
    ]
    barrier = threading.Barrier(2)

    def go(item):
        who, confirmation = item
        barrier.wait()
        return action_service.confirm(UUID(confirmation.action_id), who)

    with ThreadPoolExecutor(2) as pool:
        outcomes = list(pool.map(go, confirmations))
    assert sorted(o.success for o in outcomes) == [False, True]
    with db() as session:
        assert len(session.scalars(select(RoomBooking)).all()) == 1


# --- canteen and shuttle


def test_the_menu_is_grouped_by_meal_with_hours_and_prices(data, set_now):
    result = campus_service.canteen_menu("Monday")
    assert [m["meal"] for m in result["meals"]] == ["breakfast", "lunch", "dinner"]
    lunch = result["meals"][1]
    assert lunch["hours"] == "12:00 p.m. - 3:00 p.m." and lunch["items"][0] == {"item": "Full thali", "price": 90, "vegetarian": True}


def test_saturday_has_no_dinner_and_says_so(data, set_now):
    result = campus_service.canteen_menu("saturday")
    assert [m["meal"] for m in result["meals"]] == ["breakfast"] and "weekdays only" in result["note"]


def test_a_day_without_a_menu_says_so(data, set_now):
    result = campus_service.canteen_menu("sunday")
    assert result["meals"] == [] and "No cafeteria menu" in result["message"]


def test_the_menu_defaults_to_today_and_wants_one_day(data, set_now):
    assert campus_service.canteen_menu()["day"] == "Monday"
    assert "one day at a time" in campus_service.canteen_menu("week")["error"]
    assert "is not a day" in campus_service.canteen_menu("someday")["error"]


def test_the_next_departures_come_from_the_current_time(data, set_now):
    (route,) = campus_service.bus_schedule("A")["routes"]
    assert route["next_departures_from_first_stop"] == ["10:10", "10:50", "11:30"]
    assert route["runs_today"] and "07:00-09:30 every 20 min" in route["service_today"]


@pytest.mark.parametrize("word", ["a", "A", "Route A", "route a", "city gate"])
def test_a_route_can_be_named_loosely(data, set_now, word):
    assert [r["route_code"] for r in campus_service.bus_schedule(word)["routes"]] == ["A"]


def test_without_a_route_all_are_listed(data, set_now):
    assert [r["route_code"] for r in campus_service.bus_schedule()["routes"]] == ["A", "B", "TOWN"]


def test_an_unknown_route_is_an_error(data, set_now):
    assert "No shuttle route" in campus_service.bus_schedule("Z")["error"]


def test_sunday_only_the_hostel_loop_runs(data, set_now):
    set_now(datetime(2026, 10, 25, 9, 5))
    running = {r["route_code"]: r["runs_today"] for r in campus_service.bus_schedule()["routes"]}
    assert running == {"A": False, "B": True, "TOWN": False}


def test_the_saturday_town_shuttle_has_fixed_trips(data, set_now):
    set_now(datetime(2026, 10, 24, 11, 0))
    (town,) = campus_service.bus_schedule("town")["routes"]
    assert town["next_departures_from_first_stop"] == ["13:00", "16:00", "19:00"]
    assert town["service_today"] == ["departs 10:00, 16:00; returns 13:00, 19:00"]


def test_after_the_last_trip_nothing_is_left_today(data, set_now):
    set_now(datetime(2026, 10, 19, 23, 0))
    assert campus_service.bus_schedule("B")["routes"][0]["next_departures_from_first_stop"] == []


# --- lost and found, maintenance


def test_lost_and_found_matches_description_or_place_and_skips_claimed_items(data):
    items = campus_service.lost_and_found("umbrella")["items"]
    assert [i["description"] for i in items] == ["Black umbrella"]
    assert campus_service.lost_and_found("cafeteria")["items"][0]["description"] == "Blue water bottle"
    assert "Student Services Desk" in campus_service.lost_and_found("umbrella")["how_to_claim"]


def test_nothing_found_is_a_message_not_an_error(data):
    result = campus_service.lost_and_found("laptop")
    assert result["items"] == [] and "message" in result and "error" not in result


def test_wildcards_do_not_match_everything_in_lost_and_found(data):
    assert campus_service.lost_and_found("%")["items"] == []


def test_handing_in_an_item_adds_it_to_the_list(data, set_now, db):
    outcome = run(ASHA_PROFILE, "submit_lost_item", description="Green notebook", location_found="Library")
    assert outcome.success
    assert campus_service.lost_and_found("notebook")["items"][0]["found_on"] == "2026-10-19"
    with db() as session:
        assert session.scalar(select(LostFoundItem.reported_by).where(LostFoundItem.description == "Green notebook")) == ASHA


@pytest.mark.parametrize("args", [{"description": "x", "location_found": "Library"}, {"description": "Green notebook"}, {"description": 5, "location_found": "Library"}])
def test_a_found_item_needs_a_description_and_a_place(data, args):
    assert "I need the" in refused(ASHA_PROFILE, "submit_lost_item", **args)


def test_a_maintenance_report_is_recorded_with_a_reference(data, set_now, db):
    outcome = run(ASHA_PROFILE, "report_maintenance_issue", location="Main Academic Block, Room 214", category="Electrical", description="The projector socket sparks")
    assert outcome.details == {"Reference": "MR-00001"}
    with db() as session:
        row = session.scalar(select(MaintenanceRequest))
        assert (row.student_id, row.category, row.status, row.location) == (ASHA, "electrical", "open", "Main Academic Block, Room 214")


def test_maintenance_needs_a_known_category_and_enough_detail(data, set_now):
    assert "must be one of" in refused(ASHA_PROFILE, "report_maintenance_issue", location="Room 214", category="magic", description="Something is broken here")
    assert "description" in refused(ASHA_PROFILE, "report_maintenance_issue", location="Room 214", category="plumbing", description="leak")


def test_there_is_a_daily_limit_on_maintenance_requests(data, set_now):
    for index in range(campus_service.MAX_MAINTENANCE_PER_DAY):
        run(ASHA_PROFILE, "report_maintenance_issue", location=f"Room {index}00", category="other", description="Something is broken here")
    assert "several maintenance requests" in refused(ASHA_PROFILE, "report_maintenance_issue", location="Room 900", category="other", description="Something else is broken")
    run(RAVI_PROFILE, "report_maintenance_issue", location="Room 100", category="other", description="Another student can still report")


# --- grievances


GRIEVANCE = "The hostel mess has served the wrong meal plan for three weeks despite repeated requests."


def test_a_grievance_becomes_a_ticket_with_the_expected_timeline(data, set_now):
    outcome = run(ASHA_PROFILE, "create_grievance_ticket", category="hostel", description=GRIEVANCE)
    assert outcome.details == {"Ticket": "GR-00001"}
    status = support_service.grievance_status(ASHA, "GR-00001")
    submitted = date.fromisoformat(status["submitted"])
    assert status["status"] == "open" and status["resolution_note"] is None
    assert date.fromisoformat(status["acknowledgement_due_by"]) == support_service.add_working_days(submitted, 3)
    assert (date.fromisoformat(status["outcome_expected_by"]) - submitted).days == 28


@pytest.mark.parametrize(
    "start, days, expected",
    [(date(2026, 10, 19), 3, date(2026, 10, 22)), (date(2026, 10, 22), 3, date(2026, 10, 27)), (date(2026, 10, 24), 3, date(2026, 10, 28))],
)
def test_acknowledgement_counts_working_days_only(start, days, expected):
    assert support_service.add_working_days(start, days) == expected


@pytest.mark.parametrize(
    "text",
    [
        "I am being ragged by seniors in my hostel block every night",
        "A professor harassed me after class and I do not feel safe",
        "Someone keeps sending me threats on campus",
        "I have been bullied for weeks by classmates",
        "I feel like I want to end my life and nobody listens to me",
        "They tried to blackmail me with a photo from the trip",
    ],
)
def test_anything_about_safety_is_sent_to_real_help_and_no_ticket_is_made(data, set_now, db, text):
    reason = refused(ASHA_PROFILE, "create_grievance_ticket", category="interpersonal", description=text)
    assert "Anti-Ragging Committee" in reason and "campus security" in reason and "Counselling Centre" in reason
    with db() as session:
        assert session.scalars(select(GrievanceTicket)).all() == []


def test_the_safety_check_looks_at_the_category_too(data, set_now):
    assert "Anti-Ragging" in refused(ASHA_PROFILE, "create_grievance_ticket", category="harassment", description=GRIEVANCE)


def test_grade_disputes_go_to_the_revaluation_process(data, set_now):
    reason = refused(ASHA_PROFILE, "create_grievance_ticket", category="academic-administrative", description="I want a revaluation of my Operating Systems paper because my marks were wrong")
    assert "Examinations Cell" in reason


def test_a_grievance_needs_a_known_category_and_real_detail(data, set_now):
    assert "must be one of" in refused(ASHA_PROFILE, "create_grievance_ticket", category="gossip", description=GRIEVANCE)
    assert "description" in refused(ASHA_PROFILE, "create_grievance_ticket", category="hostel", description="bad food")


def test_status_by_ticket_number_in_any_format(data, set_now):
    run(ASHA_PROFILE, "create_grievance_ticket", category="fees", description="The fee portal charged a late fee although I paid on time.")
    for text in ("GR-00001", "gr-1", "1", " GR00001 "):
        assert support_service.grievance_status(ASHA, text)["ticket"] == "GR-00001"


def test_without_a_number_all_the_students_own_tickets_are_listed_newest_first(data, set_now):
    run(ASHA_PROFILE, "create_grievance_ticket", category="fees", description="The fee portal charged a late fee although I paid on time.")
    run(ASHA_PROFILE, "create_grievance_ticket", category="hostel", description=GRIEVANCE)
    assert [t["ticket"] for t in support_service.grievance_status(ASHA)["tickets"]] == ["GR-00002", "GR-00001"]
    assert support_service.grievance_status(RAVI)["tickets"] == []


def test_someone_elses_ticket_looks_like_one_that_does_not_exist(data, set_now):
    run(ASHA_PROFILE, "create_grievance_ticket", category="fees", description="The fee portal charged a late fee although I paid on time.")
    assert "No ticket GR-00001" in support_service.grievance_status(RAVI, "GR-00001")["error"]
    assert "looks like" in support_service.grievance_status(ASHA, "banana")["error"]


def test_an_updated_ticket_shows_its_status_and_note(data, set_now, db):
    run(ASHA_PROFILE, "create_grievance_ticket", category="fees", description="The fee portal charged a late fee although I paid on time.")
    with db.begin() as session:
        ticket = session.get(GrievanceTicket, 1)
        ticket.status, ticket.resolution_note = "resolved", "Late fee reversed."
    status = support_service.grievance_status(ASHA, "GR-00001")
    assert (status["status"], status["resolution_note"]) == ("resolved", "Late fee reversed.")


# --- counselling


def test_only_future_free_slots_are_listed_in_order(data, set_now):
    result = support_service.counselling_slots(ASHA)
    assert [s["slot_id"] for s in result["slots"]] == [2, 4]
    assert result["slots"][0] == {"slot_id": 2, "date": "2026-10-19", "weekday": "Monday", "start": "14:00", "end": "14:45"}
    assert result["your_appointment"] is None and "confidential" in result["about"]


def test_booking_a_slot_takes_it_and_shows_it_as_the_students_appointment(data, set_now):
    outcome = run(ASHA_PROFILE, "book_counselling_appointment", slot_id=2)
    assert outcome.success and "2026-10-19 at 14:00" in outcome.message
    after = support_service.counselling_slots(ASHA)
    assert [s["slot_id"] for s in after["slots"]] == [4] and after["your_appointment"]["slot_id"] == 2
    assert support_service.counselling_slots(RAVI)["your_appointment"]["slot_id"] == 3


def test_the_preview_states_the_privacy_and_place(data, set_now):
    lines = {l.label: l.value for l in action_service.propose(ASHA_PROFILE, "book_counselling_appointment", {"slot_id": 2}).lines}
    assert "Student Activity Centre" in lines["Where"] and "Confidential" in lines["Privacy"]


@pytest.mark.parametrize("slot_id, reason", [(3, "just been taken"), (1, "isn't available"), (99, "isn't available"), ("2", "slot number"), (True, "slot number"), (None, "slot number")])
def test_slots_that_are_taken_past_or_unknown_are_refused(data, set_now, slot_id, reason):
    assert reason in refused(ASHA_PROFILE, "book_counselling_appointment", slot_id=slot_id)


def test_one_upcoming_appointment_at_a_time(data, set_now):
    assert "already have an upcoming" in refused(RAVI_PROFILE, "book_counselling_appointment", slot_id=4)
    run(ASHA_PROFILE, "book_counselling_appointment", slot_id=2)
    assert "already have an upcoming" in refused(ASHA_PROFILE, "book_counselling_appointment", slot_id=4)


def test_a_past_appointment_does_not_block_a_new_one(data, set_now, db):
    with db.begin() as session:
        session.get(CounsellingSlot, 1).booked_by = ASHA
    assert run(ASHA_PROFILE, "book_counselling_appointment", slot_id=2).success


def test_two_students_for_the_last_slot_get_one_booking(data, set_now, db):
    pairs = [(p, action_service.propose(p, "book_counselling_appointment", {"slot_id": 2})) for p in (ASHA_PROFILE, ARJUN_PROFILE)]
    barrier = threading.Barrier(2)

    def go(item):
        barrier.wait()
        return action_service.confirm(UUID(item[1].action_id), item[0])

    with ThreadPoolExecutor(2) as pool:
        outcomes = list(pool.map(go, pairs))
    assert sorted(o.success for o in outcomes) == [False, True]
    with db() as session:
        assert session.get(CounsellingSlot, 2).booked_by in (ASHA, ARJUN)


# --- placement


def test_only_upcoming_drives_are_listed_with_their_criteria(data, set_now):
    result = placement_service.drives()
    assert [d["drive_id"] for d in result["drives"]] == ["PD-001", "PD-002", "PD-003"]
    first = result["drives"][0]
    assert (first["min_cgpa"], first["max_active_backlogs"], first["who_can_attend"], first["registration_open"]) == (7.0, 1, "final-year students", True)
    assert "Placement Cell" in result["note"]


def test_drives_can_be_filtered_by_company_and_dates(data, set_now):
    assert [d["drive_id"] for d in placement_service.drives(company="cobalt")["drives"]] == ["PD-003"]
    assert [d["drive_id"] for d in placement_service.drives(from_date="2026-11-05", to_date="2026-11-30")["drives"]] == ["PD-002"]
    assert placement_service.drives(company="nobody")["message"] == "No upcoming drives match."
    assert "from_date" in placement_service.drives(from_date="tomorrow")["error"]


def test_a_closed_registration_is_marked(data, set_now):
    set_now(datetime(2026, 10, 26, 9, 0))
    assert placement_service.drives(company="Northwind")["drives"][0]["registration_open"] is False


@pytest.fixture
def graded(db):
    add_academic_data(db)  # Asha's CGPA is 8.45, with no backlog


def test_a_pre_final_year_student_can_go_for_an_internship_but_not_a_full_time_drive(data, graded, set_now):
    full_time = placement_service.eligibility(ASHA, "PD-001")
    assert full_time["eligible"] is False
    year = next(c for c in full_time["checks"] if c["criterion"] == "year of study")
    assert (year["required"], year["actual"], year["met"]) == ("year 4 (final year)", "year 3", False)
    internship = placement_service.eligibility(ASHA, "PD-002")
    assert internship["eligible"] is True and all(c["met"] for c in internship["checks"])


def test_each_criterion_is_reported_separately(data, graded, set_now):
    checks = {c["criterion"]: c for c in placement_service.eligibility(ASHA, "PD-003")["checks"]}
    assert checks["department"]["met"] is False and checks["CGPA"] == {"criterion": "CGPA", "required": "at least 9.0", "actual": 8.45, "met": False}
    assert checks["active backlogs"]["met"] is True and checks["year of study"]["met"] is True


def test_a_backlog_counts_against_the_limit(data, graded, set_now, db):
    from app.db.models import AcademicRecord

    with db.begin() as session:
        session.add(AcademicRecord(student_id=ASHA, course_code="A103", semester=1, attended=30, total=40, grade="F"))
        session.add(AcademicRecord(student_id=ASHA, course_code="B301", semester=3, attended=30, total=40, grade="F"))
    checks = {c["criterion"]: c for c in placement_service.eligibility(ASHA, "PD-002")["checks"]}
    assert (checks["active backlogs"]["actual"], checks["active backlogs"]["met"]) == (2, False)


def test_without_results_the_cgpa_cannot_be_confirmed(data, set_now):
    check = next(c for c in placement_service.eligibility(ASHA, "PD-002")["checks"] if c["criterion"] == "CGPA")
    assert (check["actual"], check["met"]) == ("no results yet", False)


def test_a_company_name_picks_the_drive_or_asks_which(data, graded, set_now):
    assert placement_service.eligibility(ASHA, "cobalt")["drive"]["drive_id"] == "PD-003"
    several = placement_service.eligibility(ASHA, "northwind")
    assert [m["drive_id"] for m in several["matches"]] == ["PD-001", "PD-002"] and "Ask which" in several["message"]


def test_unknown_drives_and_students_are_errors(data, set_now):
    assert "No placement drive" in placement_service.eligibility(ASHA, "zzz")["error"]
    assert "No student record" in placement_service.eligibility("9XX99XX999", "PD-001")["error"]
    assert "No placement drive" in placement_service.eligibility(ASHA, "%")["error"]


def test_a_slot_that_started_earlier_today_is_not_offered(data, set_now):
    set_now(datetime(2026, 10, 19, 14, 30))
    assert [s["slot_id"] for s in support_service.counselling_slots(ASHA)["slots"]] == [4]


def test_the_database_itself_refuses_to_book_a_taken_slot(data, set_now, monkeypatch):
    monkeypatch.setattr(support_service, "check_counselling_booking", lambda *a: None)
    with pytest.raises(ValueError, match="just been taken"):
        support_service.book_counselling(ASHA, 3)
