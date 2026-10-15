from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.db import session as db_session
from app.db.models import Book, BookLoan, BookReservation

MAX_RESULTS = 5


def _matching(db, query: str) -> list[Book]:
    words = query.lower().split()
    haystack = func.lower(Book.title + " " + Book.author + " " + Book.isbn)
    return list(
        db.scalars(select(Book).where(*(haystack.contains(w, autoescape=True) for w in words)).order_by(Book.title))
    )


def _summary(db, book: Book) -> dict:
    due = db.scalars(select(BookLoan.due_date).where(BookLoan.book_id == book.book_id).order_by(BookLoan.due_date)).all()
    holds = db.scalar(select(func.count()).select_from(BookReservation).where(BookReservation.book_id == book.book_id))
    available = 0 if book.reference_only else book.copies_total - len(due)
    entry = {
        "book_id": book.book_id,
        "title": book.title,
        "author": book.author,
        "isbn": book.isbn,
        "shelf_location": book.shelf_location,
        "copies_total": book.copies_total,
    }
    if book.reference_only:
        entry["status"] = "reference_only"
        entry["note"] = "Reference books are read in the library and do not circulate."
        return entry
    entry.update(status="available" if available > 0 else "all_out", copies_available=available, holds_waiting=holds)
    if available <= 0 and due:
        entry["earliest_due_back"] = due[0]
    return entry


def availability(query: str) -> dict:
    """Whether a book is on the shelf, where, and if not when a copy is due back."""
    if not query.strip():
        return {"error": "Give a title, author or ISBN to look for."}
    with db_session.SessionLocal() as db:
        books = _matching(db, query)
        if not books:
            return {"error": f"No book matching '{query.strip()}' is in the catalogue."}
        result = {"books": [_summary(db, b) for b in books[:MAX_RESULTS]]}
    if len(books) > MAX_RESULTS:
        result["more_matches"] = len(books) - MAX_RESULTS
    return result


def check_reservation(student_id: str, book_id: str) -> tuple[Book, dict]:
    """The book and its current state, or a ValueError with a reason to tell the student."""
    with db_session.SessionLocal() as db:
        book = db.get(Book, book_id)
        if book is None:
            raise ValueError("I couldn't find that book. Look it up first so I have its id.")
        if book.reference_only:
            raise ValueError(f"{book.title} is a reference book: it is read in the library and cannot be borrowed or reserved.")
        summary = _summary(db, book)
        if summary["copies_available"] > 0:
            raise ValueError(
                f"A copy of {book.title} is on the shelf now ({book.shelf_location}), so there is nothing to reserve."
            )
        if db.scalar(select(func.count()).select_from(BookLoan).where(BookLoan.book_id == book_id, BookLoan.student_id == student_id)):
            raise ValueError(f"You already have a copy of {book.title} borrowed.")
        if db.scalar(select(func.count()).select_from(BookReservation).where(BookReservation.book_id == book_id, BookReservation.student_id == student_id)):
            raise ValueError(f"You already have a hold on {book.title}.")
        return book, summary


def reserve(student_id: str, book_id: str) -> int:
    """Place the hold and return the student's place in the queue."""
    check_reservation(student_id, book_id)
    with db_session.SessionLocal() as db:
        db.add(BookReservation(book_id=book_id, student_id=student_id))
        try:
            db.commit()
        except IntegrityError:
            raise ValueError("You already have a hold on this book.") from None
        return db.scalar(select(func.count()).select_from(BookReservation).where(BookReservation.book_id == book_id))
