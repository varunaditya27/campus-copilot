<div align="center">

# ⚙️ Campus Copilot — Backend

### RAG, Tool Calling, and the Agent Loop

**A FastAPI service that turns campus knowledge and structured event data into grounded answers, deterministic tool calls, and human-confirmed actions.**

<br />

[![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Python](https://img.shields.io/badge/Python-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Groq](https://img.shields.io/badge/Groq-F55036?logoColor=white)](https://groq.com/)
[![Chroma](https://img.shields.io/badge/Chroma-5B21B6?logoColor=white)](https://www.trychroma.com/)

<br />

</div>

---

## ✨ What Lives Here

This service owns everything the [frontend](../frontend/README.md) doesn't:

- **Retrieval** — the [`knowledge/`](../knowledge/README.md) corpus, embedded and searched via a local Chroma collection.
- **Tool execution** — deterministic Python functions (`search_events`, `check_event_availability`, `calculate_attendance`, `register_for_event`) that Groq can call.
- **The agent loop** — deciding, per request, whether to answer directly, call a tool, chain several tool calls, or ask the user to confirm a consequential action.
- **Structured data** — events, students, and registrations, stored in a SQL database (SQLite by default, PostgreSQL in production) and seeded from [`data/`](../data/README.md).

It's a typed REST API; it has no idea the frontend is a chat UI. For the full-system picture (why Chroma runs in-process, the overall architecture), see the [root README](../README.md).

---

## 🧠 Request Flow

```mermaid
flowchart LR
    REQ[POST /api/chat] --> RET[Retrieve from Chroma]
    RET --> LOOP{Agent loop}
    LOOP -->|tool call| TOOL[Run tool]
    TOOL --> LOOP
    LOOP -->|register_for_event| CONF[Build confirmation\nfrom real event data]
    LOOP -->|no more tool calls| ANS[Final answer]
    CONF --> RES[ChatResponse]
    ANS --> RES

    UI[User clicks Confirm] --> REG[POST /api/register]
    REG --> WRITE[(Insert registration row\n+ take one seat atomically)]
```

The important asymmetry: **every tool the model can call directly is read-only or purely computational.** The one tool that mutates data (`register_for_event`) is schema-visible to the model but not auto-executed — the agent loop intercepts that specific call and turns it into a confirmation object instead. The actual write only happens through a separate endpoint, triggered by an explicit user action. See [`app/agent/agent.py`](app/agent/agent.py).

---

## 🗂️ Project Structure

```text
backend/
├── app/
│   ├── main.py                    # FastAPI app, CORS, router wiring, /health
│   │
│   ├── api/                       # HTTP layer -- thin, no business logic
│   │   ├── auth.py                 # register, login, refresh, logout, me
│   │   ├── admin_events.py         # POST/PUT /api/admin/events (faculty, admin)
│   │   ├── chat.py                 # chat, chat/stream, history, sessions
│   │   ├── deps.py                 # get_current_student: the sign-in check
│   │   ├── events.py               # GET /api/events, /api/events/:id
│   │   ├── registration.py         # POST /api/register
│   │   └── staff.py                # registrations list and CSV export (staff, admin)
│   │
│   ├── agent/
│   │   ├── agent.py                # run_agent_stream(): the tool-calling loop, as a stream of events
│   │   ├── prompts.py              # system prompt + RAG context builder
│   │   └── tool_registry.py        # Groq tool schemas + dispatch table
│   │
│   ├── rag/
│   │   ├── ingest.py               # builds the Chroma collection from knowledge/
│   │   ├── retriever.py            # query-time retrieval + relevance cutoff
│   │   └── embeddings.py           # embedding function (local, no API key)
│   │
│   ├── db/
│   │   ├── models.py               # SQLAlchemy tables: students, events, registrations
│   │   ├── session.py              # engine + SessionLocal, built from DATABASE_URL
│   │   └── seed.py                 # loads data/*.json into empty tables
│   │
│   ├── tools/                      # functions the model can request
│   │   ├── events.py               # search_events, check_event_availability
│   │   ├── attendance.py           # calculate_attendance
│   │   └── registration.py         # register_for_event (not model-callable)
│   │
│   ├── services/                   # reusable business logic, no HTTP/LLM concerns
│   │   ├── auth_service.py         # accounts, login, refresh-token rotation
│   │   ├── chat_service.py         # sessions and message history
│   │   ├── event_service.py        # reads events from the database
│   │   └── registration_service.py # validates + writes registrations
│   │
│   ├── models/                     # Pydantic request/response schemas
│   │   ├── chat.py
│   │   ├── auth.py                 # sign-up / sign-in request and profile shapes
│   │   ├── events.py
│   │   ├── ids.py                  # student id (USN) format
│   │   └── registration.py         # a registration as staff see it
│   │
│   └── core/
│       ├── config.py                # env vars, paths -- the only os.environ access
│       ├── errors.py                # AppError + the { error_code, message, detail } handlers
│       ├── origin_check.py          # refuses state-changing requests from unknown origins (CSRF)
│       ├── security.py              # password hashing, JWT, refresh-token helpers
│       └── groq_client.py           # cached Groq client
│
├── cli.py                          # admin commands: python -m app.cli create-user
├── migrations/                     # Alembic migrations (the schema's history)
├── tests/                          # pytest suite (fake Groq client, temporary database)
├── chroma/                         # persisted vector store (gitignored, rebuilt by ingest.py)
├── alembic.ini
├── pytest.ini
├── requirements.txt
└── .env.example
```

The `api/` → `agent/`+`services/` → `tools/` split is deliberate: HTTP routes stay thin, the agent loop is reusable and testable without a running server, and `services/` functions (like `event_service`) are shared between the plain REST endpoints and the tools the model calls -- no logic is duplicated between "ask a question" and "let the model act."

---

## 🔎 RAG Pipeline

The `knowledge/` corpus (32 markdown files, simulating a complete virtual engineering university -- see [`knowledge/README.md`](../knowledge/README.md) for the full breakdown) is chunked by `##` heading rather than by raw character count, so every retrieved chunk carries a real section title (`library.md · Hours of Operation`) instead of an arbitrary offset -- the frontend's source cards display that directly.

```text
knowledge/**/*.md
      ↓  split on "## " headers
(document, section, body) chunks
      ↓  embed locally (all-MiniLM-L6-v2, no API key)
Chroma collection "campus_knowledge"
      ↓  query at chat time
top-k chunks, filtered by distance cutoff
      ↓
injected as context for Groq + returned as `sources`
```

The distance cutoff (`MAX_DISTANCE` in `core/config.py`, default `1.5`, overridable with the `RAG_MAX_DISTANCE` env var) exists because Chroma always returns its top-k nearest chunks regardless of whether any of them are actually relevant. Without it, an off-topic question would still get citations attached -- which defeats the point of showing sources at all. The threshold was calibrated empirically: on-topic queries against this corpus land at ~0.7-1.3, off-topic queries at ~1.8+.

Rebuild the index after editing `knowledge/`:

```bash
python -m app.rag.ingest
```

Safe to re-run any time -- it wipes and rebuilds the collection from scratch.

---

## 🛠️ Tools & the Agent Loop

| Tool | Model-callable? | What it does |
| --- | --- | --- |
| `search_events` | ✅ | Keyword match over structured event data (not semantic -- events have a fixed schema, so a simple match is enough) |
| `check_event_availability` | ✅ | Remaining-seats lookup |
| `calculate_attendance` | ✅ | Exact arithmetic in Python -- never trust an LLM with math it can just compute wrong |
| `register_for_event` | ⚠️ schema-visible, never auto-executed | Validates event/student/capacity/duplicate and writes the registration |

`app/agent/tool_registry.py` defines Groq's native function-calling schemas and a dispatch table (`TOOL_FUNCTIONS`) mapping name → Python callable. Only the first three tools are in that dispatch table. `register_for_event`'s schema is included so the model can request it with validated arguments (a real `event_id`; the student is always the signed-in one, never something the model supplies) -- but the agent loop special-cases that specific call, looks up the actual event, and returns a `RegistrationConfirmation` instead of executing anything.

The loop itself (`run_agent_stream()` in `agent/agent.py`, with `run_agent()` as a wrapper that waits for the final result) is bounded (`MAX_TOOL_ROUNDS = 4`) so the model can chain a few calls -- e.g. `search_events` then `check_event_availability` -- before producing a final answer, without risking an unbounded loop.

---

## 🔌 API

Matches the contract documented in [`frontend/README.md`](../frontend/README.md#-api-contract).

| Endpoint | Purpose |
| --- | --- |
| `GET /health` | Liveness check |
| `GET /api/events` | List all campus events (public) |
| `GET /api/events/{id}` | Single event, 404 if unknown (public) |
| `POST /api/auth/register` | Create an account for a student on the roster and sign them in |
| `POST /api/auth/login` | Sign in with email and password |
| `POST /api/auth/refresh` | Swap the refresh token for a new access token and refresh token |
| `POST /api/auth/logout` | Sign out and revoke the login on the server |
| `GET /api/auth/me` | The signed-in user's profile, including their role |
| `POST /api/chat` | Send a message, run the agent loop, get back a reply + sources + tool activity + optional confirmation. The exchange is saved to the caller's session |
| `POST /api/chat/stream` | Same as `POST /api/chat`, but streamed as server-sent events: tokens and tool activity arrive as they happen |
| `GET /api/chat/history` | The current session's saved messages, for restoring the chat after a refresh |
| `GET /api/chat/sessions` | The student's conversations, newest first, each with a short preview |
| `DELETE /api/chat/sessions/{id}` | Delete the student's own conversation (404 for anyone else's) |
| `POST /api/register` | Execute a registration for the signed-in student -- the only endpoint that creates registrations |

| `GET /api/staff/registrations` | Every registration with student and event details; `?event_id=` filters (staff, admin) |
| `GET /api/staff/registrations/export` | The same as a CSV download (staff, admin) |
| `POST /api/admin/events` | Create an event (faculty, admin) |
| `PUT /api/admin/events/{id}` | Edit an event (faculty for their own department's events, admin for any) |

Everything except events, health and the first three auth calls requires sign-in and answers `401 not_authenticated` otherwise. A signed-in user of the wrong role gets `403 forbidden`: the chat, sessions and registration endpoints are for students only.
Every 4xx/5xx response has the same JSON shape: `{ "error_code": "...", "message": "...", "detail": ... }`. `message` is safe to show to a user; `detail` carries field-level information for validation errors (422). Notable codes: `rate_limited` (429, Groq is throttling), `context_too_long` (413), `llm_unavailable` (502), `validation_error` (422), `not_found` (404), `internal_error` (500, no internals leaked).

Request limits: a chat `message` is 1-2000 characters; an account's `student_id` must look like a USN (e.g. `1RV23IS101`); a password is 12-128 characters.

**Streaming.** `POST /api/chat/stream` runs the same agent loop but replies with `text/event-stream`. Each event is one line, `data: {"type": ..., "payload": ...}`, followed by a blank line:

| `type` | `payload` | Meaning |
| --- | --- | --- |
| `rag_context` | `{ sources }` | Knowledge chunks found for the question (sent first) |
| `token` | `{ text }` | The next piece of the reply |
| `reset` | `{}` | The text streamed so far was a preamble to a tool call: discard it |
| `tool_start` | `{ id, tool, label }` | A tool began running |
| `tool_done` | `{ id, tool, label, status, resultSummary }` | That tool finished |
| `done` | the full `ChatResponse` | End of the stream; the exchange has been saved |
| `error` | `{ error_code, message }` | The run failed; nothing was saved |

Once streaming has started the HTTP status is already 200, so failures arrive as an `error` event; a request that is invalid from the start (for example an empty message) still gets a normal 422. The agent is a plain (sync) generator because the Groq client and the database are synchronous; Starlette runs such a generator in a worker thread, so it does not block other requests. Model tool calls arrive as fragments and are reassembled by index before they run.

**Sessions.** The server, not the browser, remembers the conversation. A student's first `POST /api/chat` creates a row in `sessions`, owned by that student, and sets a random `session_id` in an HttpOnly, `SameSite=Lax` cookie (HttpOnly means page scripts cannot read it) that remembers which conversation the browser is in. Each later request loads the session's most recent 40 messages (`HISTORY_WINDOW` in `api/chat.py`) and passes them to the agent; the reply is saved with its tool activity and sources. A failed agent run saves nothing. A session id that belongs to another student is treated as unknown, so nobody can read or continue someone else's conversation by guessing or borrowing an id. Set `COOKIE_SECURE=true` once the app is served over HTTPS.

**Authentication.** Students sign up with their USN, their name as it appears in the `students` roster, an email and a password, so an account can only be created for a real student record. Passwords are hashed with Argon2id (`pwdlib`; OWASP's preferred algorithm), and a login for an unknown email costs the same time as one for a known email and gives the same error, so neither timing nor wording reveals which accounts exist. A login sets two HttpOnly cookies: a short-lived (15 minute) signed JWT access token, and a random refresh token (14 days, only sent to `/api/auth/*`, only its hash is stored). Every refresh replaces the refresh token; presenting one that was already used (a sign of theft) revokes that whole login, apart from a 10 second grace for two tabs refreshing at once. The JWT algorithm is pinned, so unsigned or re-signed tokens are rejected. Because cookies authenticate requests, state-changing requests that carry an `Origin` header from an unknown site are refused (`OriginCheckMiddleware`), on top of `SameSite` cookies.

**Roles.** Every account has one role: `student`, `faculty`, `staff` or `admin`. Students are linked to a roster record; the others never are (a database `CHECK` enforces both). Public sign-up only ever makes students. Because anyone able to choose their own role could make themselves an admin, faculty, staff and admin accounts are created from the server with a command that prompts for the password (it is never an argument, so it stays out of shell history):

```bash
python -m app.cli create-user --role admin --name "Root Admin" --email root@campus.example
python -m app.cli create-user --role faculty --name "Dr. Rao" --email rao@campus.example \
    --department "Information Science and Engineering" --office B-204 --office-hours "Tue 2-4"
```

What each role may do: students chat, register themselves for events, and read events; staff also view and export all registrations; faculty also create events and edit their own department's (an event's `department` is set from the faculty member's, and cannot be changed by them; events with no department, including the seed events, are admin-only); admins can do everything staff and faculty can. Permissions are checked by the `require_roles(...)` dependency in `api/deps.py`. The CSV export prefixes any cell that starts with `=`, `+`, `-`, `@`, a tab or a line break with a single quote, so a hostile name cannot run as a spreadsheet formula ([OWASP: CSV injection](https://owasp.org/www-community/attacks/CSV_Injection)).

Known limits, until later roadmap phases: there is no email verification, so anyone who knows a student's USN and name can create that student's account first; and there is no login rate limiting or lockout yet. Set `JWT_SECRET` (`openssl rand -hex 32`) in production. If it is unset the server makes a temporary one, which signs everyone out on every restart.

---

## 🚀 Getting Started

```bash
cd backend
python -m venv .venv
source .venv/bin/activate      # .venv\Scripts\activate on Windows
pip install -r requirements.txt

cp .env.example .env           # add your GROQ_API_KEY

alembic upgrade head           # creates the SQLite database (backend/campus.db)
python -m app.db.seed          # loads data/*.json into it (safe to re-run)

python -m app.rag.ingest       # builds the Chroma collection (one-time; downloads
                                # a small local embedding model on first run)

uvicorn app.main:app --reload --port 8000
```

Then confirm it's alive:

```bash
curl http://localhost:8000/health
```

### Environment variables

| Variable | Default | Purpose |
| --- | --- | --- |
| `GROQ_API_KEY` | *(required)* | Your Groq API key |
| `GROQ_MODEL` | `openai/gpt-oss-120b` | Chosen for tool-use/reasoning support -- verify against `GET https://api.groq.com/openai/v1/models` before changing; Groq deprecates models over time and the docs' example model may not match what your account actually has |
| `CORS_ORIGINS` | `http://localhost:3000` | Comma-separated origins allowed to call this API |
| `DATABASE_URL` | `sqlite:///<repo>/backend/campus.db` | SQLAlchemy URL. Use `postgresql+psycopg://user:password@host:5432/dbname` for PostgreSQL |
| `JWT_SECRET` | *(random per start)* | Signs access tokens; at least 32 characters. Set it in production, otherwise every restart signs everyone out |
| `COOKIE_SECURE` | `false` | Send the session cookie over HTTPS only; set to `true` in production |
| `RAG_MAX_DISTANCE` | `1.5` | Retrieval distance cutoff; chunks farther than this are dropped. Re-calibrate if you change the embedding model or the corpus (lower is stricter) |

### Database

The schema lives in `app/db/models.py` and its history in `migrations/` (Alembic). Registrations are protected at the database level: a conditional `UPDATE` takes a seat atomically, a unique constraint on `(student_id, event_id)` blocks double booking, and a check constraint keeps `registered` within `capacity` -- so two simultaneous requests cannot both take the last seat.

```bash
alembic upgrade head                                   # apply migrations
alembic revision --autogenerate -m "describe change"   # after editing app/db/models.py
python -m app.db.seed                                  # load data/*.json into empty tables
```

Always read an autogenerated migration before applying it. For PostgreSQL, start the database from the repo root and point `DATABASE_URL` at it, then run the same two commands:

```bash
POSTGRES_PASSWORD=choose-a-password docker compose up -d postgres
export DATABASE_URL=postgresql+psycopg://campus:choose-a-password@localhost:5432/campus_copilot
```

### Running the tests

```bash
cd backend
pytest
```

The tests use a fake Groq client and a temporary copy of the data files, so they need no API key or network and never modify `data/`.

---

## 🧩 Notes for Contributors

- Keep HTTP routes in `api/` thin -- business logic belongs in `services/`, `rag/`, or `agent/`, so it can be reused and tested without spinning up a server.
- Any new tool the model should be able to call directly needs a schema in `tool_registry.TOOL_SCHEMAS` **and** an entry in `TOOL_FUNCTIONS`. If it mutates data, think hard about whether it belongs in `TOOL_FUNCTIONS` at all, or whether it needs the same confirmation-interception treatment as `register_for_event`.
- `data/events.json`, `data/students.json`, and `data/registrations.json` live at the repo root and are seed data only: `python -m app.db.seed` loads them into the database, and the app never reads or writes them at runtime. Changing the schema means editing `app/db/models.py` and generating a migration.

