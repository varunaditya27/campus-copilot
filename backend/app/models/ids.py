from typing import Annotated

from pydantic import StringConstraints

# University seat number (USN) as used in data/students.json, e.g. 1RV23IS101.
STUDENT_ID_PATTERN = r"^[0-9][A-Z]{2}[0-9]{2}[A-Z]{2}[0-9]{3}$"

StudentId = Annotated[str, StringConstraints(pattern=STUDENT_ID_PATTERN)]
