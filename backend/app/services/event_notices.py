from app.services import push_service


def seat_opened(student_id: str, event) -> None:
    """Tell a student they were moved from an event's waitlist into a seat."""
    push_service.notify(
        student_id, "A seat opened up", f"You're now registered for {event.name}, {event.date} at {event.time}.", f"/events/{event.id}"
    )
