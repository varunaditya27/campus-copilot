from pydantic import Field, validate_call

from app.models.ids import StudentId
from app.services import academic_service, directory_service, fee_service, schedule_service


@validate_call
def get_attendance_report(student_id: StudentId) -> dict:
    """The signed-in student's attendance this semester, subject by subject.
    The student id is supplied by the agent from the login, never by the model."""
    return academic_service.attendance_report(student_id)


@validate_call
def get_cgpa(student_id: StudentId) -> dict:
    """The signed-in student's SGPA per semester and CGPA, computed from their results."""
    return academic_service.cgpa(student_id)


@validate_call
def get_student_timetable(student_id: StudentId, day: str | None = Field(default=None, max_length=20)) -> dict:
    """The signed-in student's classes for a day or the week. The student id is supplied by the agent."""
    return schedule_service.timetable(student_id, day)


@validate_call
def get_exam_schedule(student_id: StudentId, semester: int | None = None) -> dict:
    """The signed-in student's exams for a semester. The student id is supplied by the agent."""
    return schedule_service.exam_schedule(student_id, semester)


@validate_call
def get_elective_options(student_id: StudentId, semester: int | None = None) -> dict:
    """The electives open to the signed-in student's department. The student id is supplied by the agent."""
    return academic_service.elective_options(student_id, semester)


@validate_call
def get_fee_dues(student_id: StudentId) -> dict:
    """What the signed-in student has paid and owes. The student id is supplied by the agent."""
    return fee_service.fee_dues(student_id)


@validate_call
def get_course_info(course_code: str = Field(min_length=1, max_length=10)) -> dict:
    """A course's credits, instructor and weekly hours. Public information, not about any student."""
    return directory_service.course_info(course_code)


@validate_call
def get_faculty_profile(query: str = Field(min_length=1, max_length=100)) -> dict:
    """A faculty member's directory entry, by faculty id or name. Public information."""
    return directory_service.faculty_profile(query)
