from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints, model_validator

from app.models.ids import StudentId

# Deliberately loose: it catches typos, not fake addresses. Proving someone
# owns an address needs a verification email (roadmap phase 6).
Email = Annotated[
    str, StringConstraints(strip_whitespace=True, max_length=254, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
]
# Length, not composition rules (NIST SP 800-63B); 128 keeps hashing cheap to bound.
Password = Annotated[str, Field(min_length=12, max_length=128)]


class RegisterRequest(BaseModel):
    student_id: StudentId
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
    email: Email
    password: Password


class LoginRequest(BaseModel):
    email: Email
    # No length rules here: a login must not leak the password policy.
    password: Annotated[str, Field(max_length=128)]


Role = Literal["student", "faculty", "staff", "admin"]


class FacultyProfile(BaseModel):
    faculty_id: str
    department: str
    office: str | None = None
    office_hours: str | None = None


class CurrentUser(BaseModel):
    """Whoever is signed in. The student or faculty fields are set only for that role."""

    user_id: int
    role: Role
    name: str
    email: str
    student_id: str | None = None
    program: str | None = None
    year: int | None = None
    faculty: FacultyProfile | None = None


class NewStaffAccount(BaseModel):
    """An account for faculty, staff or an admin. There is no public sign-up for
    these roles; an administrator creates them (see app/cli.py)."""

    role: Literal["faculty", "staff", "admin"]
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
    email: Email
    password: Password
    department: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)] | None = None
    office: Annotated[str, StringConstraints(max_length=100)] | None = None
    office_hours: Annotated[str, StringConstraints(max_length=200)] | None = None

    @model_validator(mode="after")
    def _faculty_need_a_department(self):
        if self.role == "faculty" and not self.department:
            raise ValueError("A faculty account needs a department.")
        return self


class CurrentStudent(BaseModel):
    user_id: int
    student_id: str
    name: str
    program: str
    year: int
    email: str
    # From the student's profile; the assistant uses them to personalise answers.
    semester: int | None = None
    section: str | None = None
    electives: list[str] = Field(default_factory=list)
    interests: list[str] = Field(default_factory=list)
