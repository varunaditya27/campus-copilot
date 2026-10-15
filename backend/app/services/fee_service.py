import math
from datetime import date

from sqlalchemy import select

from app.core import clock
from app.db import session as db_session
from app.db.models import FeeRecord, Student

# From the fee policy: a ten day late-payment window follows each due date, with a
# late fee of 500 rupees per week or part of a week; after it, a student may be
# barred from classes and internal assessments.
LATE_WINDOW_DAYS = 10
LATE_FEE_PER_WEEK = 500


def fee_dues(student_id: str) -> dict:
    """What the student has paid and still owes, term by term, with deadlines."""
    today = clock.today()
    with db_session.SessionLocal() as db:
        if db.get(Student, student_id) is None:
            return {"error": "No student record was found."}
        rows = db.scalars(
            select(FeeRecord).where(FeeRecord.student_id == student_id).order_by(FeeRecord.due_date, FeeRecord.id)
        ).all()

    if not rows:
        return {"terms": [], "total_outstanding": 0, "message": "No fee records were found."}

    terms: dict[str, list[FeeRecord]] = {}
    for row in rows:
        terms.setdefault(row.term, []).append(row)

    result = []
    for term, items in terms.items():
        due = date.fromisoformat(items[0].due_date)
        amount = sum(i.amount for i in items)
        paid = sum(i.paid_amount for i in items)
        outstanding = amount - paid
        entry = {
            "term": term,
            "due_date": items[0].due_date,
            "amount": amount,
            "paid": paid,
            "outstanding": outstanding,
            "unpaid_components": [
                {"component": i.component, "outstanding": i.amount - i.paid_amount} for i in items if i.paid_amount < i.amount
            ],
        }
        if outstanding == 0:
            entry["status"] = "paid"
        elif due >= today:
            entry["status"] = "upcoming"
            entry["days_until_due"] = (due - today).days
        else:
            days_late = (today - due).days
            entry["days_overdue"] = days_late
            if days_late <= LATE_WINDOW_DAYS:
                entry["status"] = "overdue_in_late_window"
                entry["late_fee"] = LATE_FEE_PER_WEEK * math.ceil(days_late / 7)
            else:
                entry["status"] = "overdue_beyond_late_window"
        result.append(entry)

    overdue = [t for t in result if t["status"].startswith("overdue")]
    response = {
        "terms": result,
        "total_outstanding": sum(t["outstanding"] for t in result),
        "overdue_outstanding": sum(t["outstanding"] for t in overdue),
        "currency": "INR",
    }
    if any(t["status"] == "overdue_beyond_late_window" for t in overdue):
        response["note"] = (
            "Fees unpaid beyond the late-payment window may lead to the student being barred from classes "
            "and internal assessments. Finance and Accounts can arrange a payment plan: contact them early."
        )
    return response
