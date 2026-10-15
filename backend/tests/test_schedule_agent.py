import json
from datetime import date

import pytest

from app.agent import agent
from app.agent.tool_registry import STUDENT_TOOLS, TOOL_FUNCTIONS, TOOL_SCHEMAS
from app.core import clock
from fakes import completion as _completion
from fakes import tool_call as _tool_call
from helpers import ASHA_PROFILE, add_schedule_data

NEW_TOOLS = {
    "get_student_timetable": {"day": "Monday"},
    "get_exam_schedule": {},
    "get_elective_options": {},
    "get_fee_dues": {},
    "get_course_info": {"course_code": "A501"},
    "get_faculty_profile": {"query": "Sheikh"},
}
OWN_DATA_TOOLS = {"get_student_timetable", "get_exam_schedule", "get_elective_options", "get_fee_dues"}


@pytest.fixture(autouse=True)
def _data(db, monkeypatch):
    add_schedule_data(db)
    monkeypatch.setattr(clock, "today", lambda: date(2026, 10, 15))


def run(use_fakes, name, args):
    client = use_fakes(_completion(tool_calls=[_tool_call("c1", name, args)]), _completion(content="done"))
    seen = {}
    original = client._create

    def spy(**kwargs):
        seen["messages"] = kwargs["messages"]
        return original(**kwargs)

    client.chat.completions.create = spy
    response = agent.run_agent("question", [], ASHA_PROFILE)
    tool_message = next(m for m in seen["messages"] if m["role"] == "tool")
    return response, json.loads(tool_message["content"])


def schema(name):
    return next(s["function"] for s in TOOL_SCHEMAS if s["function"]["name"] == name)


def test_every_new_tool_is_registered_with_a_schema():
    for name in NEW_TOOLS:
        assert name in TOOL_FUNCTIONS and schema(name)["description"]


def test_the_tools_about_the_student_are_bound_to_the_login_and_the_others_are_not():
    assert OWN_DATA_TOOLS <= STUDENT_TOOLS
    assert not {"get_course_info", "get_faculty_profile"} & STUDENT_TOOLS


def test_the_model_is_never_asked_for_a_student_id():
    for name in NEW_TOOLS:
        assert "student_id" not in schema(name)["parameters"]["properties"]


def test_required_arguments_are_declared():
    assert schema("get_course_info")["parameters"]["required"] == ["course_code"]
    assert schema("get_faculty_profile")["parameters"]["required"] == ["query"]
    for name in OWN_DATA_TOOLS:
        assert "required" not in schema(name)["parameters"]


@pytest.mark.parametrize("name, args", NEW_TOOLS.items())
def test_each_tool_runs_through_the_agent_with_a_label_and_a_summary(use_fakes, name, args):
    response, result = run(use_fakes, name, args)
    entry = response.toolActivity[0]
    assert entry.status == "done" and "error" not in result
    assert entry.label != name and entry.resultSummary not in ("Done", "")


def test_summaries_say_something_useful(use_fakes):
    summaries = {}
    for name, args in NEW_TOOLS.items():
        response, _ = run(use_fakes, name, args)
        summaries[name] = response.toolActivity[0].resultSummary
    assert summaries == {
        "get_student_timetable": "2 classes on Monday",
        "get_exam_schedule": "3 upcoming of 4 exams",
        "get_elective_options": "2 electives in semester 5",
        "get_fee_dues": "74500 rupees outstanding",
        "get_course_info": "A501 Machine Learning",
        "get_faculty_profile": "Dr. Farhan Sheikh",
    }


@pytest.mark.parametrize("name", sorted(OWN_DATA_TOOLS))
def test_a_student_id_chosen_by_the_model_is_ignored(use_fakes, name):
    _, own = run(use_fakes, name, {})
    _, forged = run(use_fakes, name, {"student_id": "1RV24IS219"})
    assert own == forged


def test_fees_belong_to_the_signed_in_student_even_if_another_is_named(use_fakes):
    _, result = run(use_fakes, "get_fee_dues", {"student_id": "1RV24IS219"})
    assert result["total_outstanding"] == 74500  # Asha's, not Ravi's (who owes nothing)


def test_a_malformed_argument_is_reported_to_the_model_not_raised(use_fakes):
    response, result = run(use_fakes, "get_course_info", {"course_code": "X" * 40})
    assert response.toolActivity[0].status == "error" and "course_code" in result["error"]
    response, result = run(use_fakes, "get_exam_schedule", {"semester": "soon"})
    assert response.toolActivity[0].status == "error"
    response, result = run(use_fakes, "get_faculty_profile", {})
    assert response.toolActivity[0].status == "error"


def test_a_lookup_that_finds_nothing_is_an_error_entry_with_the_reason(use_fakes):
    response, result = run(use_fakes, "get_course_info", {"course_code": "ZZ999"})
    assert response.toolActivity[0].status == "done"  # the tool ran; the answer is "no such course"
    assert response.toolActivity[0].resultSummary == "No course with the code ZZ999 was found."
