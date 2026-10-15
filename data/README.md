<div align="center">

# 🗃️ Campus Copilot — Structured Data

### The Application State the Agent Can Search, Check, and Change

**JSON seed data modeling the live, mutable side of the virtual university — events, students, and registrations — loaded into the application database by `python -m app.db.seed`, as distinct from the static [knowledge corpus](../knowledge/README.md) the agent retrieves from.**

<br />

[![JSON](https://img.shields.io/badge/JSON-000000?logo=json&logoColor=white)](https://www.json.org/)

<br />

</div>

---

## ✨ What Lives Here

Two kinds of information feed Campus Copilot, and they are deliberately kept apart:

- **Static knowledge** ([`knowledge/`](../knowledge/README.md)) — policy, process, and "how does this place work" material. Slow-changing, embedded into Chroma, retrieved semantically.
- **Structured data** (this directory) — facts with an identity, a current state, and the possibility of changing *during a conversation*. An event has a seat count that goes down. A registration either exists or doesn't. No embedding model should ever be asked to "recall" whether a specific seat is still free — that's a lookup, not retrieval.

This is why `search_events` and `check_event_availability` are Python functions querying this data directly (see [`backend/README.md`](../backend/README.md#-tools--the-agent-loop)), not RAG. The distinction is one of the core teaching points of the whole project.

The files are seed data. At runtime the app reads and writes the database tables they seed, never the files themselves.

| File | Seeds table | Changed at runtime by |
| --- | --- | --- |
| `events.json` | `events` | an approved registration increments `registered` |
| `students.json` | `students` | nothing at runtime — a fixed roster |
| `registrations.json` | `registrations` | an approved registration inserts a row |
| `courses.json` | `courses` | nothing at runtime -- the course catalogue |
| `student_profiles.json` | `student_profiles` | `PUT /api/students/me/profile` changes interests |
| `academic_records.json` | `student_academic_records` | nothing at runtime -- attendance and grades |
| `faculty_members.json` | `faculty_members` | nothing at runtime -- the public faculty directory (separate from `faculty`, the sign-in accounts) |
| `course_offerings.json` | `course_offerings` | nothing at runtime -- who teaches each course and its weekly hours |
| `timetable_slots.json` | `timetable_slots` | nothing at runtime -- the weekly timetable of each class group |
| `exams.json` | `exams` | nothing at runtime -- internal tests, practicals and end-semester exams |
| `fee_records.json` | `fee_records` | nothing at runtime -- what each student owes and has paid |
| `books.json` | `books` | nothing at runtime -- the library catalogue (titles and authors are real; the ISBNs are placeholders) |
| `book_loans.json` | `book_loans` | nothing at runtime -- which copies are out, and to whom |
| `canteen_menu.json` | `canteen_menu` | nothing at runtime -- the weekly cafeteria menu |
| `study_rooms.json` | `study_rooms` | nothing at runtime -- the eight discussion rooms |
| `bus_routes.json` | `bus_routes` | nothing at runtime -- shuttle routes and service windows |
| `lost_found_items.json` | `lost_found_items` | a student handing in an item adds a row |
| `counselling_slots.json` | `counselling_slots` | booking an appointment sets `booked_by` |
| `placement_drives.json` | `placement_drives` | nothing at runtime -- upcoming drives and their criteria |
| `event_details.json` | `event_details` | nothing at runtime -- the prerequisites and materials of each seeded event (invented) |

The seeded events are dated August and September 2026, so from mid-October 2026 they count as past: they can be given feedback on but not cancelled or waitlisted. Events created through the admin API behave normally.

Reservations, room bookings, maintenance requests and grievance tickets have no seed file: they start empty and are created by approved actions.

---

## 🎟️ `events.json`

18 events, evenly split — three per category — across the six categories the schema supports (`artificial-intelligence`, `web-development`, `competitive-programming`, `cybersecurity`, `research`, `robotics`), dated across a five-week window so both "what's happening tomorrow" and "what's happening next month" have real answers. Organizers and venues are drawn from entities the [knowledge corpus](../knowledge/README.md) already names — the Coding Club, the AI and Machine Learning Community, the Centre for AI and Data Systems, the Cybersecurity Research Lab, the Embedded Systems and IoT Lab — so a question that needs both a retrieved fact (what does that lab focus on?) and a live lookup (when's its next event, and is it full?) exercises the full agent loop, not just one half of it.

The event schema (`backend/app/models/events.py` and `frontend/lib/types.ts`, kept in sync by hand) is:

```jsonc
{
  "id": "evt_ai_001",
  "name": "AI Odyssey: Building with Generative AI",
  "category": "artificial-intelligence",
  "date": "2026-08-21",       // YYYY-MM-DD
  "time": "15:00",            // HH:MM, 24h
  "duration_minutes": 120,
  "venue": "Innovation and Computing Centre - Seminar Hall",
  "capacity": 50,
  "registered": 33,
  "organizer": "AI and Machine Learning Community",
  "description": "...",
  "tags": ["AI", "LLM", "RAG", "generative-ai", "workshop", "technical"]
}
```

`category` is a closed `Literal` type on both ends — adding a new category means updating the type in *both* `backend/app/models/events.py` and `frontend/lib/types.ts`, not just adding a new string here. `registered` is a baseline seat count independent of `registrations.json`; it represents demand from students outside this demo's own registration flow, so a fresh event doesn't read as suspiciously empty.

---

## 🎓 `students.json`

20 students, four per department, spread evenly across all four years — enough to make "check whether this student exists" a real lookup rather than a single hardcoded happy path. Student IDs follow an illustrative `1RV{admission-year}{dept-code}{number}` pattern (`1RV23IS101`), matching the department vocabulary in [`knowledge/campus/departments-and-programs.md`](../knowledge/campus/departments-and-programs.md).

```jsonc
{
  "student_id": "1RV23IS101",
  "name": "Aarav Sharma",
  "program": "Information Science and Engineering",
  "year": 3
}
```

This is intentionally the *entire* student record. There's no email, no password, no personal data beyond a name — the corpus repeatedly makes the point (see [`knowledge/policies/digital-conduct-and-computing.md`](../knowledge/policies/digital-conduct-and-computing.md)) that Campus Copilot should never handle sensitive personal data, and the demo dataset is built to match that: there's simply nothing sensitive here to leak.

---

## 📝 `registrations.json`

The append-only log that approved registrations are written to (see [`backend/app/services/registration_service.py`](../backend/app/services/registration_service.py)). Ships with four seed entries so the app doesn't start in a completely empty state, and so a fresh reader can see the shape without registering for anything first.

```jsonc
{
  "registration_id": "REG-DEMO-001",
  "student_id": "1RV23IS101",
  "event_id": "evt_web_002",
  "registered_at": "2026-08-18T14:20:00+05:30",
  "status": "confirmed"
}
```

`registration_id` for anything created through the app follows `REG-{n:05d}`, continuing from this file's length — the `REG-DEMO-*` prefix on the seed rows exists only to make it obvious at a glance which entries were shipped versus created live during a demo.

---

## 🗓️ Faculty, timetable, exams and fees

`python data/generate_schedule_data.py` (run after `generate_academic_data.py`) writes `faculty_members.json`, `course_offerings.json`, `timetable_slots.json`, `exams.json` and `fee_records.json`, deterministically.

What comes from the knowledge documents: the 35 faculty names, designations, specialisations, Head of Department and Vice-Chair roles, and department office rooms (parsed from `knowledge/campus/faculty-and-departments-directory.md`), and the fee amounts, instalments and due dates (July 15 and December 15, half the annual structure per semester, with the 2,000 rupee a year consumables supplement for ECE and Mechanical). **Invented for the demo:** each person's office room, office hours and email (`@campus.example`), which faculty member teaches which course (round robin within the department, so it does not follow specialisation), the timetable, and every exam date and venue. The dates assume the odd semester of 2026-27; `schedule_service` and `fee_service` compare them with the real date, so as time passes everything shows as past or overdue until the generator's dates are moved.

The timetable keeps every class group (department, semester, section) free of clashes and gives each course the hours it declares. It does not stop a teacher being in two places at once: a department has about seven faculty and far more weekly hours than that, so a realistic teacher timetable would need more people than the directory has. The deliberate fee cases: Ananya Iyer never paid the odd semester's laboratory fee (past the late-payment window), Aditya Verma paid part of the tuition, and Priya Menon paid the even semester early. The tests rerun the generator and compare it with the committed files, and check the files against the rules above.

---

## 🏛️ Campus operations data

`python data/generate_operations_data.py` writes the library, menu, rooms, shuttle, lost and found, counselling and placement files, deterministically, for the date 2026-10-15. Shapes come from the knowledge documents: eight rooms seating four to eight, a fourteen day loan, reference books that never circulate, the cafeteria's four meals and the 60 and 90 rupee prices, the three shuttle routes and the Saturday town shuttle, and placement criteria with CGPA thresholds between 6.0 and 7.5 and at most one active backlog. **Invented:** every menu item and its price (apart from those two), the loans, the lost items, the counselling slots (weekday afternoons; the documents give walk-ins on weekday mornings and appointments through the Student Services Desk, but no times), the drives and their companies (all fictional), and the placeholder ISBNs (`DEMO-0001`: the real numbers are not in the sources used). There is no counsellor name anywhere.

Two documents disagree and the more specific one is followed: `dining-and-transport.md` says the shuttle runs every 15 minutes at peak and not on Sundays, while `transportation-routes.md` gives each route its own frequency and has Route B running every day including weekends; the data follows the routes document. Dates assume mid-October 2026, so drives and slots become past as time moves on until the generator's dates are moved.

---

## 🎓 `courses.json`, `student_profiles.json` and `academic_records.json`

The academic side of the demo university: 228 courses (the five departments, eight semesters each, with names taken from the subject lists in [the curriculum document](../knowledge/academics/curriculum-and-degree-structure.md)), a profile for each of the 20 students (current semester, section, electives, interests), and 478 records of attendance and grades. A student in year Y is in semester 2Y - 1, because the odd semester is running; grades exist for completed semesters and attendance so far for the current one.

These files are **generated**, not written by hand: `python data/generate_academic_data.py` from the repository root rewrites them, deterministically (a fixed random seed), so the output is committed and a re-run produces identical files. The generator adds a few deliberate cases so the assistant has something to say: Aarav Sharma's Machine Learning attendance is 72%, inside the 65-74% range where condonation can be applied for, with one more subject just under 75%; Arjun Reddy has one backlog (an F in semester 2); and Aditya Verma is at 58% in one subject, below the 65% line. The tests check the files for consistency (every record names a real course in the right semester, grades exist exactly for completed semesters) and run the real calculations over them.

---

## 🧩 Notes for Contributors

- Keep `events.json` categories inside the six the `Literal` type allows — the backend will reject anything else at load time, loudly, which is the point.
- If you add a department, event, or student, prefer reusing entities already named in the [knowledge corpus](../knowledge/README.md) (a department, a lab, a community) over inventing new ones — the two datasets being mutually consistent is what makes cross-referencing questions ("who runs the Cybersecurity Research Lab's next event?") answerable at all.
- `registered` on an event is not derived from `registrations.json` — don't expect the two to reconcile to the same number. That's deliberate: one is baseline demand, the other is this app's own action log.
- After editing these files, no rebuild step is required — unlike the knowledge corpus, they're read fresh on every request (see `event_service.list_events()`), not indexed.
