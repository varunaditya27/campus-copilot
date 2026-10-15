import json

import pytest
from pydantic import ValidationError

from app.agent import agent
from app.agent.prompts import SYSTEM_PROMPT, build_student_message
from app.agent.tool_registry import STUDENT_TOOLS, TOOL_FUNCTIONS, TOOL_SCHEMAS
from app.models.auth import CurrentStudent
from app.tools.academic import get_attendance_report, get_cgpa
from fakes import completion as _completion
from fakes import tool_call as _tool_call
from helpers import ASHA_PROFILE, add_academic_data

RAVI_PROFILE = CurrentStudent(
    user_id=2, student_id="1RV24IS219", name="Ravi", program="CSE", year=2, email="ravi@example.com"
)


def run_and_get_tool_message(use_fakes, call, student=ASHA_PROFILE):
    client = use_fakes(_completion(tool_calls=[call]), _completion(content="done"))
    seen = {}
    original = client._create

    def spy(**kwargs):
        seen["messages"] = kwargs["messages"]
        return original(**kwargs)

    client.chat.completions.create = spy
    response = agent.run_agent("my attendance?", [], student)
    tool = next(m for m in seen["messages"] if m["role"] == "tool")
    return response, json.loads(tool["content"])


# --- the tools themselves


def test_the_tools_check_their_input():
    for tool in (get_attendance_report, get_cgpa):
        with pytest.raises(ValidationError):
            tool("not a student id")


def test_the_tools_are_registered_and_take_no_arguments_from_the_model():
    names = {s["function"]["name"]: s["function"]["parameters"] for s in TOOL_SCHEMAS}
    for name in ("get_attendance_report", "get_cgpa"):
        assert name in TOOL_FUNCTIONS and name in STUDENT_TOOLS
        assert names[name]["properties"] == {}, "the model must not be asked for a student id"


def test_other_tools_are_not_student_bound():
    for name in ("search_events", "check_event_availability", "calculate_attendance", "get_course_info", "get_faculty_profile"):
        assert name in TOOL_FUNCTIONS and name not in STUDENT_TOOLS


# --- identity comes from the login, never from the model


def test_the_students_own_data_is_used(db, use_fakes):
    add_academic_data(db)
    response, result = run_and_get_tool_message(use_fakes, _tool_call("c1", "get_attendance_report", {}))
    assert {c["course_code"] for c in result["courses"]} == {"A501", "A502", "A503"}
    assert response.toolActivity[0].status == "done"


def test_a_student_id_the_model_supplies_is_ignored(db, use_fakes):
    add_academic_data(db)
    # The model (perhaps misled by something in the conversation) asks for Ravi's data.
    _, result = run_and_get_tool_message(
        use_fakes, _tool_call("c1", "get_attendance_report", {"student_id": "1RV24IS219"})
    )
    assert {c["course_code"] for c in result["courses"]} == {"A501", "A502", "A503"}, "got Asha's, not Ravi's"
    assert "B301" not in json.dumps(result)


def test_the_same_request_from_another_student_gets_their_own_data(db, use_fakes):
    add_academic_data(db)
    _, result = run_and_get_tool_message(
        use_fakes, _tool_call("c1", "get_attendance_report", {"student_id": "1RV23IS101"}), student=RAVI_PROFILE
    )
    assert {c["course_code"] for c in result["courses"]} == {"B301"}


def test_cgpa_is_also_bound_to_the_signed_in_student(db, use_fakes):
    add_academic_data(db)
    _, result = run_and_get_tool_message(use_fakes, _tool_call("c1", "get_cgpa", {"student_id": "1RV24IS219"}))
    assert result["cgpa"] == 8.45  # Asha's, although the model asked for Ravi's


def test_other_unexpected_arguments_are_still_refused(db, use_fakes):
    add_academic_data(db)
    response, result = run_and_get_tool_message(use_fakes, _tool_call("c1", "get_cgpa", {"semester": 1}))
    assert response.toolActivity[0].status == "error" and "error" in result


def test_the_signed_in_students_id_cannot_be_swapped_by_malformed_input(db, use_fakes):
    response, result = run_and_get_tool_message(use_fakes, _tool_call("c1", "get_cgpa", {"student_id": ["a", "b"]}))
    assert response.toolActivity[0].status == "done" and "error" not in result  # ignored, so no harm


# --- what the student sees in the activity log


def test_the_attendance_tool_is_labelled_and_summarised(db, use_fakes):
    add_academic_data(db)
    response, _ = run_and_get_tool_message(use_fakes, _tool_call("c1", "get_attendance_report", {}))
    assert response.toolActivity[0].label == "Checking your attendance records"
    assert response.toolActivity[0].resultSummary == "2 of 3 subjects below 75%"


def test_the_cgpa_tool_is_labelled_and_summarised(db, use_fakes):
    add_academic_data(db)
    response, _ = run_and_get_tool_message(use_fakes, _tool_call("c1", "get_cgpa", {}))
    assert (response.toolActivity[0].label, response.toolActivity[0].resultSummary) == ("Calculating your CGPA", "CGPA 8.45")


def test_a_student_with_no_results_is_told_so(db, use_fakes):
    add_academic_data(db)
    response, _ = run_and_get_tool_message(use_fakes, _tool_call("c1", "get_cgpa", {}), student=RAVI_PROFILE)
    assert response.toolActivity[0].resultSummary == "No results yet"


def test_both_tools_can_run_in_the_same_turn(db, use_fakes):
    add_academic_data(db)
    use_fakes(
        _completion(tool_calls=[_tool_call("a", "get_attendance_report", {}), _tool_call("b", "get_cgpa", {})]),
        _completion(content="both"),
    )
    response = agent.run_agent("attendance and cgpa", [], ASHA_PROFILE)
    assert [a.tool for a in response.toolActivity] == ["get_attendance_report", "get_cgpa"]
    assert [a.status for a in response.toolActivity] == ["done", "done"]


# --- what the model is told


def test_the_prompt_tells_the_model_not_to_guess_personal_figures():
    assert "get_attendance_report" in SYSTEM_PROMPT and "get_cgpa" in SYSTEM_PROMPT
    assert "never state a personal academic figure" in SYSTEM_PROMPT


def student_with(**fields):
    return CurrentStudent(user_id=1, student_id="1RV23IS101", name="Asha", program="ISE", year=3, email="a@x.com", **fields)


def test_the_persona_names_the_student_year_branch_and_semester():
    text = build_student_message(student_with(semester=5, section="B"))
    assert "Asha" in text and "1RV23IS101" in text and "year 3" in text and "ISE" in text
    assert "semester 5" in text and "section B" in text


def test_the_persona_lists_electives_and_interests_when_known():
    text = build_student_message(student_with(semester=5, electives=["Machine Learning"], interests=["artificial-intelligence", "web-development"]))
    assert "Machine Learning" in text and "artificial intelligence, web development" in text


def test_the_persona_leaves_out_what_is_not_known():
    text = build_student_message(student_with())
    assert "semester" not in text and "electives" not in text and "interested" not in text


def test_the_persona_reaches_the_model(use_fakes):
    client = use_fakes(_completion(content="hi"))
    seen = {}
    original = client._create

    def spy(**kwargs):
        seen["messages"] = kwargs["messages"]
        return original(**kwargs)

    client.chat.completions.create = spy
    agent.run_agent("hi", [], student_with(semester=5, interests=["robotics"]))

    system_text = " ".join(m["content"] for m in seen["messages"] if m["role"] == "system")
    assert "semester 5" in system_text and "robotics" in system_text
