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
    LOOP -->|register_for_event| CONF[Check it, store it as a pending action,\nbuild the confirmation card]
    LOOP -->|no more tool calls| ANS[Final answer]
    CONF --> RES[ChatResponse]
    ANS --> RES

    UI[User clicks Confirm] --> REG[POST /api/actions/id/confirm]
    REG --> WRITE[(Run the stored action:\ninsert registration + take one seat atomically)]
```

The important asymmetry: **every tool the model can call directly is read-only or purely computational.** The one tool that mutates data (`register_for_event`) is schema-visible to the model but not auto-executed — the agent loop intercepts that specific call and turns it into a confirmation object instead. The model's request is checked and stored on the server as a *pending action* (the parameters live in the database, not in the browser, so what the student approves is exactly what runs). The actual write only happens through `POST /api/actions/{id}/confirm`, triggered by an explicit user action. Each action is an `ActionSpec` in `app/actions/` (schema, `prepare`, `execute`), so new write actions plug into the same approval path. A pending action expires after 10 minutes, runs at most once however many times or how simultaneously it is confirmed, and can only be confirmed by the student it was made for. See [`app/agent/agent.py`](app/agent/agent.py).

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
│   │   ├── admin_knowledge.py      # knowledge base and retrieval evaluation (admin)
│   │   ├── chat.py                 # chat, chat/stream, history, sessions
│   │   ├── deps.py                 # get_current_student: the sign-in check
│   │   ├── events.py               # GET /api/events, /api/events/:id
│   │   ├── actions.py              # POST /api/actions/{id}/confirm and /cancel
│   │   ├── students.py             # the student's own profile
│   │   └── staff.py                # registrations list and CSV export (staff, admin)
│   │
│   ├── agent/
│   │   ├── agent.py                # the agent as a LangGraph graph; run_agent_stream() streams its events
│   │   ├── prompts.py              # system prompt + RAG context builder
│   │   └── tool_registry.py        # Groq tool schemas + dispatch table
│   │
│   ├── rag/
│   │   ├── chunking.py             # heading-aware chunks of at most 256 tokens
│   │   ├── ingest.py               # incremental build of the store from knowledge/
│   │   ├── store.py                # the vector store (Chroma or Qdrant) behind one small interface
│   │   ├── lexical.py              # BM25 keyword search
│   │   ├── fusion.py               # Reciprocal Rank Fusion
│   │   ├── pdf.py                  # text of a PDF, as markdown with a section per page
│   │   ├── rerank.py               # cross-encoder reranker
│   │   ├── retriever.py            # the search pipeline and relevance cutoff
│   │   ├── evaluate.py             # scores retrieval against rag_eval/golden.json
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
│   │   ├── academic_service.py     # profiles, attendance, CGPA and elective options
│   │   ├── schedule_service.py     # timetable and exam schedule
│   │   ├── fee_service.py          # fee dues and late fees
│   │   ├── directory_service.py    # course information and the faculty directory
│   │   ├── chat_service.py         # sessions and message history
│   │   ├── entity_service.py       # what a conversation has mentioned (events, courses, faculty)
│   │   ├── summary_service.py      # cached conversation summaries
│   │   ├── knowledge_service.py    # uploads, ingest, status and deletion of documents
│   │   ├── rag_eval_service.py     # runs the retrieval evaluation in the background
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
├── rag_eval/                       # golden questions and the log of evaluation runs
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

The `knowledge/` corpus (32 markdown files, simulating a complete virtual engineering university -- see [`knowledge/README.md`](../knowledge/README.md) for the full breakdown) is chunked along its headings, so every retrieved chunk carries a real section title (`library.md · Hours of Operation`) -- the frontend's source cards display that directly.

```text
knowledge/**/*.md
      ↓  split on ## and ### headings, then into chunks of at most 256 tokens
chunks that each start with "Document - Section", so they make sense alone
      ↓  embed locally (all-MiniLM-L6-v2, no API key)
Chroma collection "campus_knowledge"

at question time:
      ↓  search by meaning (top 30)        search by words, BM25 (top 30)
      ↓  merged with Reciprocal Rank Fusion
      ↓  a cross-encoder reads the question with each of the best 10 and re-orders them
      ↓  top 3, dropping any the reranker scores below RAG_RERANK_MIN_SCORE
injected as context for Groq + returned as `sources`
```

**Why each stage exists.** Every choice was measured against a set of 92 questions with known answers (`rag_eval/golden.json`; `python -m app.rag.evaluate`). Semantic search copes with rephrased questions but is weak on exact names and numbers ("Where is Room 318?"); keyword search is the reverse; merging them helps, but it is the cross-encoder, which reads question and passage together, that puts the right passage on top. Scores on that set (`rag_eval/history.jsonl` keeps every run):

| Retrieval | Right passage in top 3 | Right passage first | Exact-name questions in top 3 |
| --- | --- | --- | --- |
| Semantic search only, `##` chunks (the starting point) | 89.1% | 65.2% | 71.4% |
| + keyword search and reranking, 256-token chunks | **97.8%** | **82.6%** | **100%** |

The off-topic test questions (weather, recipes) also went from 90% to 100% correctly receiving no passages. Three findings that shaped the design:

- **Chunks are at most 256 tokens** because that is all the embedding model reads; it silently cuts off anything longer (Chroma's code and the model card both say so), so a longer chunk would be partly invisible to semantic search. On this corpus 256 scored at least as well as 128, 192 and the 512 initially suggested.
- **Each chunk is prefixed with its document and section**, which improved the right passage being first from 66.7% to 75.6% for semantic search alone.
- **The relevance threshold comes from the reranker's scores**: its best passage for every question in the set scored at least -7.1 on topic and at most -9.9 off topic, so `RAG_RERANK_MIN_SCORE` is -8.5. A threshold cannot separate "about the library" from "answers this question about the library", so campus-related questions the documents do not cover (a cafeteria menu, a phone number) still receive some passages; the prompt tells the model to say when the material does not contain the answer.

**Choosing a vector database.** By default the knowledge base is Chroma, kept in files under `CHROMA_DIR` (no server to run). Set `CHROMA_HOST` (and `CHROMA_PORT`) to use a Chroma server instead, or `VECTOR_STORE=qdrant` (with `QDRANT_URL`, and `QDRANT_API_KEY` if the server needs one) to use Qdrant. Retrieval and ingestion only use a small interface (`VectorStore` in `rag/store.py`), embeddings are computed in the backend with the same model whichever database stores them, and one test suite runs against both, so they behave the same: on the evaluation set, local Chroma, a Chroma server and Qdrant all score Recall@3 0.978. `docker-compose.yml` has both servers behind profiles, bound to localhost because neither has authentication switched on:

```bash
docker compose --profile qdrant up -d qdrant          # or: --profile chroma-server up -d chroma
VECTOR_STORE=qdrant python -m app.rag.ingest          # or: CHROMA_HOST=localhost CHROMA_PORT=8100
```

Changing the database starts an empty knowledge base there, so run ingest after switching. If the database cannot be reached, the server logs it and answers without campus documents, as it does when the knowledge base has not been built.

Operating it:

```bash
python -m app.rag.ingest          # adds and updates only documents whose files changed
python -m app.rag.ingest --full   # wipes the store and rebuilds everything
python -m app.rag.evaluate        # scores retrieval; add --log "what changed" to record it
pytest -m slow                    # the same scores as a test, with the real models (about a minute)
```

Ingestion records a hash of each file and the chunking settings; a run skips documents that match, re-embeds ones that do not, and removes chunks of deleted files. Changing `CHUNK_TOKENS`, `CHUNK_OVERLAP` or the embedding model is detected, so stale chunks are never left behind. Identical chunks are stored once.

Things to know: the first start downloads the reranker (about 80 MB, ONNX, no PyTorch) and the models are loaded at startup, so the first question is not slow; a question then takes about 0.3 seconds to retrieve for. The keyword index is built in memory from the store (about 260 chunks, milliseconds), and refreshed within 5 seconds of the store changing, so it can never disagree with it. If the knowledge base has not been built, the server starts anyway and answers without campus documents, saying so.

---

## 🛠️ Tools & the Agent Loop

| Tool | Model-callable? | What it does |
| --- | --- | --- |
| `search_events` | ✅ | Keyword match over structured event data (not semantic -- events have a fixed schema, so a simple match is enough) |
| `check_event_availability` | ✅ | Remaining-seats lookup |
| `calculate_attendance` | ✅ | Exact arithmetic in Python -- never trust an LLM with math it can just compute wrong |
| `get_attendance_report` | ✅ (about the signed-in student) | Attendance this semester, subject by subject, which are below the 75% required and how many classes it would take to reach it |
| `get_cgpa` | ✅ (about the signed-in student) | SGPA per completed semester, CGPA (credit-weighted, a failed course counts as zero points), and any backlogs |
| `get_student_timetable` | ✅ (about the signed-in student) | Classes for today, tomorrow, a named weekday or the whole week, with times and rooms, for the student's own section |
| `get_exam_schedule` | ✅ (about the signed-in student) | Internal tests, practicals and end-semester exams for the current (or a named) semester, each marked past, today or upcoming |
| `get_elective_options` | ✅ (about the signed-in student) | Electives offered to the student's department in a semester, marking the ones they take, with the add/drop rule |
| `get_fee_dues` | ✅ (about the signed-in student) | Paid and outstanding fees per term, due dates, and the late fee (500 rupees a week or part of one) inside the ten day late window |
| `get_course_info` | ✅ (public) | A course's credits, semester, kind, instructor and weekly hours. The syllabus itself is not in the data: the tool points to the instructor's course handout |
| `get_faculty_profile` | ✅ (public) | Designation, department, specialisation, office, office hours, email and courses taught, found by name or id. A shared surname returns the candidates instead of guessing |
| `register_for_event` | ⚠️ schema-visible, never auto-executed | Validates event/student/capacity/duplicate and writes the registration |

The tools about the student's own records (attendance, CGPA, timetable, exams, electives, fees) take no student id from the model. The agent supplies the student's id from the login and discards any `student_id` the model puts in its call, so a model that is confused or misled by text in the conversation cannot look up someone else's attendance or grades. Their figures come from SQL and Python, never from the model, and the prompt tells the model not to state a personal academic figure it did not get from a tool.

`app/agent/tool_registry.py` defines Groq's native function-calling schemas and a dispatch table (`TOOL_FUNCTIONS`) mapping name → Python callable. Every tool except `register_for_event` is in that dispatch table. `register_for_event`'s schema is included so the model can request it with validated arguments (a real `event_id`; the student is always the signed-in one, never something the model supplies) -- but the agent loop special-cases that specific call, looks up the actual event, and returns a `RegistrationConfirmation` instead of executing anything.

The agent is a [LangGraph](https://docs.langchain.com/oss/python/langgraph) state graph (`agent/agent.py`), with `run_agent_stream()` streaming its events and `run_agent()` waiting for the final result:

```text
retrieve → (plan) → reason ──→ respond                       the model answered
                      ↑   ├──→ request_confirmation → respond   it asked to register someone
                      │   └──→ execute_tools ──→ reason        results go back to the model
                      └────────────────────────→ respond       out of rounds
```

- **State** (`AgentState`): the messages so far, the retrieved passages, pending tool calls, the tool activity, any pending confirmation, the reply, and `loop_count`. Nodes return only what they add.
- **Nodes** do one job each: `retrieve` (knowledge search), `reason` (one model call, streaming tokens), `execute_tools`, `request_confirmation` (the human-approval gate: registering is never executed, only turned into a confirmation card), `respond` (the final `done` event). Each node reports progress through LangGraph's stream writer, as the same events described under Streaming below.
- **Decisions** are three small named functions, `is_confirmation_needed`, `should_call_tools` and `is_done`, combined by the routing functions, so the rules are easy to read and test.
- **Bounded:** the model gets at most `MAX_TOOL_ROUNDS = 4` turns, counted in the state. Behind that, `RECURSION_LIMIT` makes LangGraph itself stop a run that takes too many steps, so a routing mistake cannot loop forever. (LangGraph has no cycle detection; this limit is its equivalent.)
- **Parallel tools:** when the model asks for several tools in one turn they run at the same time, in threads, because they are independent. Events are still sent from the node's own thread, results keep the order of the calls, and one failing tool does not stop the others.
- **Planning (off by default):** with `AGENT_PLANNING=true` a `plan` node first asks the model to split a multi-step request into steps and shows the plan to the model. It adds a model call to every question and has not been shown to help, so it stays off until there is an evaluation of tool use to prove it.


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
| `GET /api/students/me/profile` | The student's record and profile: program, year, semester, section, electives, interests (students) |
| `PUT /api/students/me/profile` | Change interests; nothing else about the profile can be changed this way (students) |
| `GET /api/chat/sessions` | The student's conversations, newest first, each with a short preview |
| `GET /api/chat/sessions/{id}/summary` | Two or three sentences on what a conversation was about (the student's own; cached until the conversation grows) |
| `DELETE /api/chat/sessions/{id}` | Delete the student's own conversation (404 for anyone else's) |
| `POST /api/actions/{id}/confirm` | Approve a pending action the assistant proposed (for example a registration) and run it, once |
| `POST /api/actions/{id}/cancel` | Decline a pending action; nothing is done |

| `GET /api/staff/registrations` | Every registration with student and event details; `?event_id=` filters (staff, admin) |
| `GET /api/staff/registrations/export` | The same as a CSV download (staff, admin) |
| `POST /api/admin/knowledge/ingest` | Bring the knowledge base up to date; `?full=true` wipes and rebuilds it (admin) |
| `POST /api/admin/knowledge/upload` | Add a `.md` or `.pdf` document without a rebuild (admin) |
| `GET /api/admin/knowledge/status` | Collection name, document and chunk counts, last ingest time, each document's source (admin) |
| `DELETE /api/admin/knowledge/{name}` | Remove an uploaded document (admin) |
| `POST /api/admin/rag/eval` | Start scoring retrieval against the golden questions (admin); read the result from `GET /api/admin/rag/eval` |
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

**Personalisation.** Each student has a profile (semester, section, electives, interests) and academic records (attendance and grades per course). When a chat request starts, the profile is loaded with the student, and the assistant's context says who they are: name, year, branch, current semester, electives and interests. Interests are editable on the profile page; the rest comes from the student record. The data is demo data, generated by `data/generate_academic_data.py` (see [`data/README.md`](../data/README.md)).

**Conversation memory.** A chat remembers what it has been about, so a follow-up like "register me for it" knows what "it" is. After each exchange the events, courses and faculty members mentioned (by the student or the assistant) are recorded for that conversation, and the most recent few of each kind are shown to the model at the start of the next turn, with the ids it needs for a tool call. Finding them takes no model call: events are matched against the events table (by id, name, or the part of the name before a colon), courses against the catalogue (by code, or by name for the student's own department only, since a name like "Machine Learning" is taught by two departments), and faculty against the names in the knowledge documents. So it is instant, and it can only find things that exist. Memory belongs to one conversation, is deleted with it, and a failure while recording it never fails the chat. `GET /api/chat/sessions/{id}/summary` asks the model for a short summary of one of the student's conversations; it is saved on the session and only written again once the conversation has grown. The model sees the conversation's most recent 60 messages, each cut to 600 characters.

**Sessions.** The server, not the browser, remembers the conversation. A student's first `POST /api/chat` creates a row in `sessions`, owned by that student, and sets a random `session_id` in an HttpOnly, `SameSite=Lax` cookie (HttpOnly means page scripts cannot read it) that remembers which conversation the browser is in. Each later request loads the session's most recent 40 messages (`HISTORY_WINDOW` in `api/chat.py`) and passes them to the agent; the reply is saved with its tool activity and sources. A failed agent run saves nothing. A session id that belongs to another student is treated as unknown, so nobody can read or continue someone else's conversation by guessing or borrowing an id. Set `COOKIE_SECURE=true` once the app is served over HTTPS.

**Authentication.** Students sign up with their USN, their name as it appears in the `students` roster, an email and a password, so an account can only be created for a real student record. Passwords are hashed with Argon2id (`pwdlib`; OWASP's preferred algorithm), and a login for an unknown email costs the same time as one for a known email and gives the same error, so neither timing nor wording reveals which accounts exist. A login sets two HttpOnly cookies: a short-lived (15 minute) signed JWT access token, and a random refresh token (14 days, only sent to `/api/auth/*`, only its hash is stored). Every refresh replaces the refresh token; presenting one that was already used (a sign of theft) revokes that whole login, apart from a 10 second grace for two tabs refreshing at once. The JWT algorithm is pinned, so unsigned or re-signed tokens are rejected. Because cookies authenticate requests, state-changing requests that carry an `Origin` header from an unknown site are refused (`OriginCheckMiddleware`), on top of `SameSite` cookies.

**Roles.** Every account has one role: `student`, `faculty`, `staff` or `admin`. Students are linked to a roster record; the others never are (a database `CHECK` enforces both). Public sign-up only ever makes students. Because anyone able to choose their own role could make themselves an admin, faculty, staff and admin accounts are created from the server with a command that prompts for the password (it is never an argument, so it stays out of shell history):

```bash
python -m app.cli create-user --role admin --name "Root Admin" --email root@campus.example
python -m app.cli create-user --role faculty --name "Dr. Rao" --email rao@campus.example \
    --department "Information Science and Engineering" --office B-204 --office-hours "Tue 2-4"
```

What each role may do: students chat, register themselves for events, and read events; staff also view and export all registrations; faculty also create events and edit their own department's (an event's `department` is set from the faculty member's, and cannot be changed by them; events with no department, including the seed events, are admin-only); admins can do everything staff and faculty can. Permissions are checked by the `require_roles(...)` dependency in `api/deps.py`. The CSV export prefixes any cell that starts with `=`, `+`, `-`, `@`, a tab or a line break with a single quote, so a hostile name cannot run as a spreadsheet formula ([OWASP: CSV injection](https://owasp.org/www-community/attacks/CSV_Injection)).

**Managing the knowledge base.** Admins can update what the assistant knows without touching the server. The curated corpus in `knowledge/` stays under version control; documents added through the API are kept apart in `backend/knowledge_uploads/` (gitignored, `KNOWLEDGE_UPLOAD_DIR`) and are searched along with it. An upload is a `.md` file, or a `.pdf` whose text is read with `pypdf` and stored as markdown with a section per page (a scanned PDF has no text and is refused; password-protected ones too); uploading a name again replaces the earlier one. File names are restricted to letters, digits, spaces, dots, dashes and underscores with no folders, the size limit is 10 MB, an upload cannot replace a curated document, and curated documents cannot be deleted through the API (change the file in the repository and ingest again). Only one ingest runs at a time. The evaluation takes about a minute, so `POST /api/admin/rag/eval` starts it in the background and `GET` returns `idle`, `running`, `done` (with the report) or `failed`; the state belongs to one server process, so with several workers ask the one that started it.

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

python -m app.rag.ingest       # builds the knowledge base (downloads a small local
                                # embedding model on first run; the first server start
                                # downloads the reranker, about 80 MB)

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
| `AGENT_PLANNING` | `false` | Plan multi-step requests before answering (adds a model call per question; unproven, so off) |
| `COOKIE_SECURE` | `false` | Send the session cookie over HTTPS only; set to `true` in production |
| `RAG_TOP_K` | `3` | How many passages the agent receives per question |
| `RAG_RRF_K` | `60` | Reciprocal Rank Fusion constant (the value from the original paper) |
| `RAG_RERANK_MIN_SCORE` | `-8.5` | Passages the reranker scores below this are not given to the model. Re-check with `python -m app.rag.evaluate` if you change the corpus or the reranker (higher is stricter) |
| `VECTOR_STORE` | `chroma` | `chroma` or `qdrant` |
| `CHROMA_DIR` | `backend/chroma` | Where local Chroma keeps its files |
| `CHROMA_HOST`, `CHROMA_PORT` | *(unset)*, `8000` | Use a Chroma server instead of local files when the host is set |
| `QDRANT_URL`, `QDRANT_API_KEY` | `http://localhost:6333`, *(unset)* | Where Qdrant is, when `VECTOR_STORE=qdrant` |
| `KNOWLEDGE_UPLOAD_DIR` | `backend/knowledge_uploads` | Where documents uploaded through the admin API are kept |

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

