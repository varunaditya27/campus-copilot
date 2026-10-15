import csv
import io
from typing import Annotated

from fastapi import APIRouter, Query, Response

from app.api.deps import StaffUser
from app.core.errors import AppError
from app.models.registration import RegistrationRecord
from app.services import event_service, registration_service

router = APIRouter(prefix="/api/staff", tags=["staff"])

EventFilter = Annotated[str | None, Query(max_length=64)]

CSV_COLUMNS = list(RegistrationRecord.model_fields)

# Spreadsheets treat a cell starting with one of these as a formula (CSV injection).
_FORMULA_STARTS = ("=", "+", "-", "@", "\t", "\r", "\n", "\uff1d", "\uff0b", "\uff0d", "\uff20")


def _safe_cell(value: object) -> str:
    text = str(value)
    # A leading single quote makes the spreadsheet read the cell as plain text.
    return "'" + text if text.startswith(_FORMULA_STARTS) else text


def _records(event_id: str | None) -> list[RegistrationRecord]:
    if event_id is not None and event_service.get_event(event_id) is None:
        raise AppError(404, "not_found", f"Event '{event_id}' not found")
    return registration_service.list_registrations(event_id)


@router.get("/registrations")
def registrations(user: StaffUser, event_id: EventFilter = None) -> list[RegistrationRecord]:
    return _records(event_id)


@router.get("/registrations/export")
def export_registrations(user: StaffUser, event_id: EventFilter = None) -> Response:
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(CSV_COLUMNS)
    for record in _records(event_id):
        writer.writerow([_safe_cell(value) for value in record.model_dump().values()])
    return Response(
        content=out.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="registrations.csv"'},
    )
