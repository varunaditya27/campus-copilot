from app.models.ids import StudentId
from app.services import academic_service
from pydantic import validate_call


@validate_call
def get_attendance_report(student_id: StudentId) -> dict:
    """The signed-in student's attendance this semester, subject by subject.
    The student id is supplied by the agent from the login, never by the model."""
    return academic_service.attendance_report(student_id)


@validate_call
def get_cgpa(student_id: StudentId) -> dict:
    """The signed-in student's SGPA per semester and CGPA, computed from their results."""
    return academic_service.cgpa(student_id)
