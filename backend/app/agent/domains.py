from app.agent.tool_registry import TOOL_SCHEMAS

# Which tools (and actions) each specialist sees. Every tool belongs to exactly one
# domain; a test checks that none is left out.
DOMAIN_TOOLS: dict[str, frozenset[str]] = {
    "academic": frozenset(
        {
            "get_attendance_report", "get_cgpa", "calculate_attendance", "get_student_timetable",
            "get_exam_schedule", "get_elective_options", "get_fee_dues", "get_course_info",
            "get_faculty_profile", "get_placement_drives", "check_placement_eligibility",
        }
    ),
    "events": frozenset(
        {
            "search_events", "check_event_availability", "get_event_detail", "get_my_registrations",
            "get_event_feedback_form", "register_for_event", "cancel_event_registration",
            "join_event_waitlist", "submit_event_feedback",
        }
    ),
    "library": frozenset(
        {"check_library_availability", "reserve_library_book", "check_study_room_availability", "book_study_room"}
    ),
    "grievance": frozenset(
        {"create_grievance_ticket", "get_grievance_status", "get_counselling_slots", "book_counselling_appointment"}
    ),
    "general": frozenset(
        {"get_canteen_menu", "get_bus_schedule", "get_lost_and_found", "submit_lost_item", "report_maintenance_issue"}
    ),
}

DOMAIN_DESCRIPTIONS = {
    "academic": "the student's own academics and money: timetable, attendance, CGPA, exams, electives, fees, courses, faculty, placement drives and eligibility",
    "events": "campus events: finding them, details, registering, cancelling, waitlists, feedback, the student's registrations",
    "library": "the library: finding or reserving books, and booking discussion rooms",
    "grievance": "complaints and support: raising or checking a grievance, counselling appointments, anything about ragging, harassment, safety or distress",
    "general": "everything else on campus: canteen, shuttle, lost and found, maintenance problems, and general questions about campus rules and facilities",
}

SPECIALIST_PROMPTS = {
    domain: f"You are the specialist for {description}. Use your tools for these; for any other campus question, answer from the campus knowledge you are given, or say it is outside what you can help with."
    for domain, description in DOMAIN_DESCRIPTIONS.items()
}


def allowed_tools(domain: str | None) -> frozenset[str] | None:
    """The tool names a specialist may use, or None for the single agent that may use all."""
    return DOMAIN_TOOLS[domain] if domain else None


def schemas_for(domain: str | None) -> list[dict]:
    if not domain:
        return TOOL_SCHEMAS
    return [s for s in TOOL_SCHEMAS if s["function"]["name"] in DOMAIN_TOOLS[domain]]
