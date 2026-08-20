from app.services import registration_service


def register_for_event(student_id: str, event_id: str) -> dict:
    return registration_service.create_registration(student_id, event_id)
