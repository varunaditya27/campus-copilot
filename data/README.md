<div align="center">

# 🗃️ Campus Copilot — Structured Data

### The Application State the Agent Can Search, Check, and Change

**Plain JSON modeling the live, mutable side of the virtual university — events, students, and registrations — as distinct from the static [knowledge corpus](../knowledge/README.md) the agent retrieves from.**

<br />

[![JSON](https://img.shields.io/badge/JSON-000000?logo=json&logoColor=white)](https://www.json.org/)

<br />

</div>

---

## ✨ What Lives Here

Two kinds of information feed Campus Copilot, and they are deliberately kept apart:

- **Static knowledge** ([`knowledge/`](../knowledge/README.md)) — policy, process, and "how does this place work" material. Slow-changing, embedded into Chroma, retrieved semantically.
- **Structured data** (this directory) — facts with an identity, a current state, and the possibility of changing *during a conversation*. An event has a seat count that goes down. A registration either exists or doesn't. No embedding model should ever be asked to "recall" whether a specific seat is still free — that's a lookup, not retrieval.

This is why `search_events` and `check_event_availability` are Python functions reading these files directly (see [`backend/README.md`](../backend/README.md#-tools--the-agent-loop)), not RAG. The distinction is one of the core teaching points of the whole project.

| File | Shape | Mutated by |
| --- | --- | --- |
| `events.json` | list of `CampusEvent` | `POST /api/register` increments `registered` |
| `students.json` | list of student records | nothing at runtime — a fixed roster |
| `registrations.json` | list of registration records | `POST /api/register` appends |

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

The append-only log `POST /api/register` writes to (see [`backend/app/services/registration_service.py`](../backend/app/services/registration_service.py)). Ships with four seed entries so the app doesn't start in a completely empty state, and so a fresh reader can see the shape without registering for anything first.

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

## 🧩 Notes for Contributors

- Keep `events.json` categories inside the six the `Literal` type allows — the backend will reject anything else at load time, loudly, which is the point.
- If you add a department, event, or student, prefer reusing entities already named in the [knowledge corpus](../knowledge/README.md) (a department, a lab, a community) over inventing new ones — the two datasets being mutually consistent is what makes cross-referencing questions ("who runs the Cybersecurity Research Lab's next event?") answerable at all.
- `registered` on an event is not derived from `registrations.json` — don't expect the two to reconcile to the same number. That's deliberate: one is baseline demand, the other is this app's own action log.
- After editing these files, no rebuild step is required — unlike the knowledge corpus, they're read fresh on every request (see `event_service.list_events()`), not indexed.
