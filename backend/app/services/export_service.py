import csv
import io
from collections.abc import Iterable, Sequence

# Spreadsheets treat a cell starting with one of these as a formula (CSV injection).
_FORMULA_STARTS = ("=", "+", "-", "@", "\t", "\r", "\n", "＝", "＋", "－", "＠")


def safe_cell(value: object) -> str:
    text = "" if value is None else str(value)
    # A leading single quote makes the spreadsheet read the cell as plain text.
    return "'" + text if text.startswith(_FORMULA_STARTS) else text


def to_csv(columns: Sequence[str], rows: Iterable[Sequence[object]]) -> str:
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(columns)
    for row in rows:
        writer.writerow([safe_cell(value) for value in row])
    return out.getvalue()
