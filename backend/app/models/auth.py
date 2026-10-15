from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints

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


class CurrentStudent(BaseModel):
    user_id: int
    student_id: str
    name: str
    program: str
    year: int
    email: str
