from typing import Annotated

from fastapi import APIRouter, Query, UploadFile

from app.api.deps import AdminUser
from app.services import student_admin_service

router = APIRouter(prefix="/api/admin/students", tags=["admin"])

READ_CHUNK = 64 * 1024


@router.get("")
def list_students(
    admin: AdminUser,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=student_admin_service.MAX_PAGE_SIZE)] = 25,
    q: Annotated[str | None, Query(max_length=100)] = None,
    program: Annotated[str | None, Query(max_length=100)] = None,
    year: Annotated[int | None, Query(ge=1, le=4)] = None,
) -> dict:
    return student_admin_service.list_students(page, page_size, q, program, year)


@router.get("/{student_id}")
def student_detail(student_id: str, admin: AdminUser) -> dict:
    return student_admin_service.student_detail(student_id)


@router.post("/import", status_code=201)
def import_students(admin: AdminUser, file: UploadFile) -> dict:
    """Add students from a CSV file (columns: student_id, name, program, year)."""
    data = bytearray()
    while chunk := file.file.read(READ_CHUNK):
        data += chunk
        if len(data) > student_admin_service.MAX_IMPORT_BYTES:
            break  # import_students rejects it with the proper error
    return student_admin_service.import_students(bytes(data))
