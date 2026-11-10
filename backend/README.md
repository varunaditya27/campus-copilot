<div align="center">

# Backend

The API, the agent, retrieval, security and background jobs of Campus Copilot.

</div>

---

## What Lives Here

This service owns everything the [frontend](../frontend/README.md) does not. The [architecture](../docs/architecture.md) shows how the parts fit together.

- Retrieval: the [`knowledge/`](../knowledge/README.md) corpus, embedded and searched by meaning and by words.
- Tools: deterministic Python functions the model can ask for, and ten actions that change data only after the student approves them.
- The agent loop: deciding, for each question, whether to answer directly, call tools, chain several of them, or propose an action for approval.
- Data: students, events, registrations, academic records and campus services in a SQL database (SQLite by default, PostgreSQL in production), seeded from [`data/`](../data/README.md).
- Notifications and background jobs: web push, a calendar file, and the scheduled reminders and attendance warnings.

It is a typed REST API. It does not know the frontend is a chat screen.

---

## Request Flow

<p align="center"><img src="../docs/diagrams/chat-flow.svg" alt="Sequence of a chat question: the browser asks the API, the agent searches the knowledge store, asks the language model, runs any tool it requests in a loop, and the reply streams back to the browser." width="100%"></p>

The important asymmetry: every tool the model can call directly only reads data or computes something. The ten actions that change data are never run by the agent. The agent loop turns a request for one into a stored proposal and a confirmation card, and the action runs only when the student approves it. See [actions need a yes](../docs/architecture.md#actions-need-a-yes).

---

## Project Structure

Everything is under `backend/app/`, one folder per concern.

- `main.py`: the FastAPI app, middleware and router wiring, and `/health`.
- `api/`: the HTTP routes. They stay thin and hold no business logic.
- `agent/`: the LangGraph graph, the prompts, the tool registry, and the optional router and specialists.
- `actions/`: the ten actions that wait for approval. Each one checks itself when it is proposed and again when it is approved.
- `tools/`: the functions the model may call directly. They read data or compute something and never change anything.
- `services/`: the business logic, one module per concern, with no HTTP or model details.
- `rag/`: chunking, ingestion, the vector stores, keyword search, rank fusion, the reranker, the retriever and its evaluation.
- `llm/`: the model providers (Groq, OpenAI, Ollama) and the quality tiers.
- `db/`: the SQLAlchemy tables, the session, and the loader for the sample data.
- `models/`: the Pydantic request and response shapes.
- `security/`: rate limits, the prompt injection screen, admin API keys, security headers and the start-up settings check.
- `observability/`: structured logs, metrics, tracing and error reporting.
- `core/`: settings, the clock (campus time), errors, password and token helpers, and the origin check.
- `worker.py`: the Celery app and its two scheduled jobs.
- `cli.py`: administration commands such as `create-user`, `create-admin-key` and `create-vapid-keys`.

Next to `app/` are `migrations/` (the schema's history, with Alembic), `tests/`, `rag_eval/` (the golden questions and the log of evaluation runs) and `chroma/` (the stored vectors, git-ignored and rebuilt by ingest).

The split between `api/`, then `agent/` and `services/`, then `tools/` is deliberate: routes stay thin, the agent loop can be tested without a server, and the business rules are written once.

---

## RAG Pipeline

The `knowledge/` corpus (32 markdown files, simulating a complete virtual engineering university -- see [`knowledge/README.md`](../knowledge/README.md) for the full breakdown) is chunked along its headings, so every retrieved chunk carries a real section title (`library.md · Hours of Operation`) -- the frontend's source cards display that directly.

<p align="center"><img src="../docs/diagrams/retrieval.svg" alt="Retrieval pipeline: the question is searched by meaning and by words, the two lists are merged, the best are reranked, and only passages above the cutoff reach the prompt." width="100%"></p>

Building the store, once per change to the documents:

- Each file in `knowledge/` is split on its `##` and `###` headings, then into chunks of at most 256 tokens.
- Each chunk starts with "Document - Section", so it makes sense on its own.
- Each chunk is embedded locally (`all-MiniLM-L6-v2`, no API key) and stored in the Chroma collection `campus_knowledge`.

Answering a question:

- A search by meaning and a search by words (BM25) each return their top 30.
- The two lists are merged with reciprocal rank fusion.
- A cross-encoder reads the question with each of the best 10 and re-orders them.
- The top 3 are kept, dropping any the reranker scores below `RAG_RERANK_MIN_SCORE`.
- They are given to the model as context and returned as `sources`.

Why each stage exists. Every choice was measured against a set of 92 questions with known answers (`rag_eval/golden.json`; `python -m app.rag.evaluate`). Semantic search copes with rephrased questions but is weak on exact names and numbers ("Where is Room 318?"); keyword search is the reverse; merging them helps, but it is the cross-encoder, which reads question and passage together, that puts the right passage on top. Scores on that set (`rag_eval/history.jsonl` keeps every run):

| Retrieval | Right passage in top 3 | Right passage first | Exact-name questions in top 3 |
| --- | --- | --- | --- |
| Semantic search only, `##` chunks (the starting point) | 89.1% | 65.2% | 71.4% |
| + keyword search and reranking, 256-token chunks | 97.8% | 82.6% | 100% |

The off-topic test questions (weather, recipes) also went from 90% to 100% correctly receiving no passages. Three findings that shaped the design:

- Chunks are at most 256 tokens because that is all the embedding model reads; it silently cuts off anything longer (Chroma's code and the model card both say so), so a longer chunk would be partly invisible to semantic search. On this corpus 256 scored at least as well as 128, 192 and the 512 initially suggested.
- Each chunk is prefixed with its document and section, which improved the right passage being first from 66.7% to 75.6% for semantic search alone.
- The relevance threshold comes from the reranker's scores: its best passage for every question in the set scored at least -7.1 on topic and at most -9.9 off topic, so `RAG_RERANK_MIN_SCORE` is -8.5. A threshold cannot separate "about the library" from "answers this question about the library", so campus-related questions the documents do not cover (a cafeteria menu, a phone number) still receive some passages; the prompt tells the model to say when the material does not contain the answer.

Choosing a vector database. By default the knowledge base is Chroma, kept in files under `CHROMA_DIR` (no server to run). Set `CHROMA_HOST` (and `CHROMA_PORT`) to use a Chroma server instead, or `VECTOR_STORE=qdrant` (with `QDRANT_URL`, and `QDRANT_API_KEY` if the server needs one) to use Qdrant. Retrieval and ingestion only use a small interface (`VectorStore` in `rag/store.py`), embeddings are computed in the backend with the same model whichever database stores them, and one test suite runs against both, so they behave the same: on the evaluation set, local Chroma, a Chroma server and Qdrant all score Recall@3 0.978. `docker-compose.yml` has both servers behind profiles, bound to localhost because neither has authentication switched on:

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

## Tools & the Agent Loop

| Tool | Model-callable? | What it does |
| --- | --- | --- |
| `search_events` | yes | Keyword match over structured event data (not semantic -- events have a fixed schema, so a simple match is enough) |
| `check_event_availability` | yes | Remaining-seats lookup |
| `calculate_attendance` | yes | Exact arithmetic in Python -- never trust an LLM with math it can just compute wrong |
| `get_attendance_report` | yes (about the signed-in student) | Attendance this semester, subject by subject, which are below the 75% required and how many classes it would take to reach it |
| `get_cgpa` | yes (about the signed-in student) | SGPA per completed semester, CGPA (credit-weighted, a failed course counts as zero points), and any backlogs |
| `get_student_timetable` | yes (about the signed-in student) | Classes for today, tomorrow, a named weekday or the whole week, with times and rooms, for the student's own section |
| `get_exam_schedule` | yes (about the signed-in student) | Internal tests, practicals and end-semester exams for the current (or a named) semester, each marked past, today or upcoming |
| `get_elective_options` | yes (about the signed-in student) | Electives offered to the student's department in a semester, marking the ones they take, with the add/drop rule |
| `get_fee_dues` | yes (about the signed-in student) | Paid and outstanding fees per term, due dates, and the late fee (500 rupees a week or part of one) inside the ten day late window |
| `get_course_info` | yes (public) | A course's credits, semester, kind, instructor and weekly hours. The syllabus itself is not in the data: the tool points to the instructor's course handout |
| `get_faculty_profile` | yes (public) | Designation, department, specialisation, office, office hours, email and courses taught, found by name or id. A shared surname returns the candidates instead of guessing |
| `check_library_availability` | yes (public) | A book by title, author or ISBN: copies on the shelf, shelf location, earliest return and holds waiting. Reference books are marked as not borrowable |
| `check_study_room_availability` | yes (public) | The eight library discussion rooms and their free two-hour blocks on a date, up to three days ahead (Saturday hours are shorter; Sunday is closed) |
| `get_canteen_menu` | yes (public) | The cafeteria menu for a day, by meal with hours and prices (dinner is weekdays only) |
| `get_bus_schedule` | yes (public) | Routes A, B, C and the Saturday town shuttle: stops, today's service and the next departures from the current time |
| `get_lost_and_found` | yes (public) | Search unclaimed lost items |
| `get_grievance_status` | yes (about the signed-in student) | The student's own tickets, status, resolution note, and the policy dates (acknowledgement in three working days, outcome in four weeks) |
| `get_counselling_slots` | yes (about the signed-in student) | Free counselling slots and the student's own upcoming appointment |
| `get_placement_drives` | yes (public) | Upcoming drives with deadlines and criteria |
| `check_placement_eligibility` | yes (about the signed-in student) | Year, department, CGPA and backlogs checked one by one against a drive's criteria |
| `reserve_library_book`, `book_study_room`, `report_maintenance_issue`, `submit_lost_item`, `create_grievance_ticket`, `book_counselling_appointment` | no, an action: never auto-executed | Each is checked, stored as a pending action and shown on a confirmation card; only the student's approval runs it (see below) |
| `get_event_detail` | yes (about the signed-in student) | Organiser, description, prerequisites, materials to bring, seats left, waitlist length, and whether the student is registered or waiting |
| `get_my_registrations` | yes (about the signed-in student) | The student's registrations (with ids and past or upcoming) and waitlist places |
| `get_event_feedback_form` | yes (about the signed-in student) | The feedback form (a 1-5 rating and optional comments) and whether the student can fill it in now |
| `cancel_event_registration`, `join_event_waitlist`, `submit_event_feedback` | no, an action: never auto-executed | Cancel (only before the event starts), join the waitlist of a full event, send feedback (only for an event the student was registered for and which has started, once) |
| `register_for_event` | no: schema-visible, never auto-executed | Validates event/student/capacity/duplicate and writes the registration |

The tools about the student's own records (attendance, CGPA, timetable, exams, electives, fees) take no student id from the model. The agent supplies the student's id from the login and discards any `student_id` the model puts in its call, so a model that is confused or misled by text in the conversation cannot look up someone else's attendance or grades. Their figures come from SQL and Python, never from the model, and the prompt tells the model not to state a personal academic figure it did not get from a tool.

`app/agent/tool_registry.py` defines the function-calling schemas and a dispatch table (`TOOL_FUNCTIONS`) mapping each name to a Python callable. Every read-only or computational tool is in that table. The ten actions are not: their schemas are included so the model can request one with validated arguments (a real id, and the student is always the signed-in one, never something the model supplies), but the agent loop never runs it. It stores a proposal and returns a confirmation card, and the action in `actions/` runs only when the student approves it.

Cancelling and the waitlist. Cancelling deletes the registration and frees the seat in one transaction. If students are waiting, the first in line is registered in that same transaction, automatically, so a freed seat is never left empty; the confirmation card warns the student cancelling that this will happen. Two simultaneous cancellations free one seat, because the delete only counts if exactly one row went.

Rules the actions enforce (each is checked when proposed and again when approved, since time passes): a hold is only for a title with no copy on the shelf; rooms are two-hour blocks within library hours, up to three days ahead, one student per slot (the database refuses a double booking); a counselling slot goes to one student and a student keeps one upcoming appointment; at most five maintenance requests a day. A grievance ticket is refused, with pointers to real help, if it could involve ragging, harassment, a threat to safety or someone in distress (the Anti-Ragging Committee, the Internal Complaints Committee, the hostel warden, the Dean of Student Affairs, campus security, the Counselling Centre), because the policy puts those above every routine process, and if it is a grade dispute (those follow the revaluation process). The screen is a deliberately broad keyword check on top of the model's own judgement, so it will sometimes refuse an innocent message; that is the safe direction to err in.

The agent is a [LangGraph](https://docs.langchain.com/oss/python/langgraph) state graph (`agent/agent.py`), with `run_agent_stream()` streaming its events and `run_agent()` waiting for the final result:

The graph runs like this:

- `retrieve`, then `plan` if planning is on, then `reason`.
- From `reason`, if the model answered, the graph goes to `respond`.
- If the model asked for an action, the graph goes to `request_confirmation` and then `respond`.
- If the model asked for tools, the graph goes to `execute_tools` and back to `reason`, with the results.
- If the rounds run out, the graph goes to `respond`.

- State (`AgentState`): the messages so far, the retrieved passages, pending tool calls, the tool activity, any pending confirmation, the reply, and `loop_count`. Nodes return only what they add.
- Nodes do one job each: `retrieve` (knowledge search), `reason` (one model call, streaming tokens), `execute_tools`, `request_confirmation` (the human-approval gate: registering is never executed, only turned into a confirmation card), `respond` (the final `done` event). Each node reports progress through LangGraph's stream writer, as the same events described under Streaming below.
- Decisions are three small named functions, `is_confirmation_needed`, `should_call_tools` and `is_done`, combined by the routing functions, so the rules are easy to read and test.
- Bounded: the model gets at most `MAX_TOOL_ROUNDS = 4` turns, counted in the state. Behind that, `RECURSION_LIMIT` makes LangGraph itself stop a run that takes too many steps, so a routing mistake cannot loop forever. (LangGraph has no cycle detection; this limit is its equivalent.)
- Parallel tools: when the model asks for several tools in one turn they run at the same time, in threads, because they are independent. Events are still sent from the node's own thread, results keep the order of the calls, and one failing tool does not stop the others.
- Multiple agents (off by default): with `MULTI_AGENT=true` a LangGraph *supervisor* (`agent/supervisor.py`) puts a router in front of the agent. The router asks the model which of five domains the message belongs to (`academic`, `events`, `library`, `grievance`, `general`; the tools of each are listed in `agent/domains.py`) and the supervisor sends the message to that specialist: the same agent graph, but offered only its domain's tools and told its focus. A specialist that asks for a tool outside its domain gets an error instead of a result, and cannot propose an action outside it. If the message spans domains ("find me an event and check my attendance") the router names up to three, the specialists run in parallel (one LangGraph `Send` each), and a final model call merges their answers into one reply, keeping every confirmation card; if that merge call fails the specialists' own answers are joined instead. A lone specialist streams exactly like the single agent; with several, only tool activity shows live (under ids prefixed with the domain) and the merged answer streams at the end. If the router's reply cannot be read, the single agent with every tool handles the message. It costs one extra model call per question (two for a compound one), and it has not been compared with the single agent on real traffic, so it is off until an evaluation shows it helps.
- Planning (off by default): with `AGENT_PLANNING=true` a `plan` node first asks the model to split a multi-step request into steps and shows the plan to the model. It adds a model call to every question and has not been shown to help, so it stays off until there is an evaluation of tool use to prove it.


---

## API

The frontend's [README](../frontend/README.md#how-it-talks-to-the-backend) describes how the page uses these endpoints, including the chat's streaming events.

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
| `GET /api/students/me/calendar.ics` | The events the student is registered for as a calendar file (`.ics`) that Google, Apple and Outlook calendars import. Times are read as Asia/Kolkata (students) |
| `GET /api/notifications/public-key` | The key a browser needs to subscribe to push notifications; `404 push_unavailable` when push is not set up (students) |
| `POST /api/notifications/subscribe` | Save this browser's push subscription for the student. Only the browsers' own push services are accepted as the address (students) |
| `POST /api/notifications/unsubscribe` | Forget a browser's subscription; only the student's own can be removed (students) |
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
| `DELETE /api/admin/events/{id}` | Delete an event. With registrations it answers `409 event_has_registrations` until called with `?force=true`, which also removes the registrations, waitlist and feedback (same rule on departments) |
| `GET /api/admin/events/{id}/registrations` | The event, everyone registered (with student details) and the waitlist in order |
| `POST /api/admin/events/{id}/registrations/export` | The registrations as a CSV download, with spreadsheet formulas neutralised |
| `GET /api/admin/students` | Paged roster (`page`, `page_size` up to 100) with `q` (id or name) and `program`, `year` filters (admin) |
| `GET /api/admin/students/{id}` | One student in full: account, CGPA and backlogs, every course record, registrations, grievance tickets (admin) |
| `POST /api/admin/students/import` | Add students from a CSV (`student_id, name, program, year`). All or nothing: one bad row imports nothing and every problem is reported; students already on the roster are skipped and listed (admin) |
| `GET /api/admin/knowledge/{name}/chunks` | A document's chunks with character and word counts, and the embedding model, vector size and collection (admin) |
| `GET /api/admin/grievances` | All tickets with their student, newest first, with counts per status; `?status=` filters (staff, admin) |
| `PUT /api/admin/grievances/{id}` | Set a ticket's status (`open`, `in_progress`, `resolved`) and resolution note; resolving needs a note. The student is emailed when the status changes (staff, admin) |
| `GET /api/admin/analytics` | Usage over the last `?days=` (1-365, default 30): daily active students, questions per session, tool and document use, common words, approval rate of proposed actions, zero-context replies (admin) |

Everything except events, health and the first three auth calls requires sign-in and answers `401 not_authenticated` otherwise. A signed-in user of the wrong role gets `403 forbidden`: the chat, sessions and registration endpoints are for students only.
Every 4xx/5xx response has the same JSON shape: `{ "error_code": "...", "message": "...", "detail": ... }`. `message` is safe to show to a user; `detail` carries field-level information for validation errors (422). Notable codes: `rate_limited` (429, Groq is throttling), `context_too_long` (413), `llm_unavailable` (502), `validation_error` (422), `not_found` (404), `internal_error` (500, no internals leaked).

Request limits: a chat `message` is 1-2000 characters; an account's `student_id` must look like a USN (e.g. `1RV23IS101`); a password is 12-128 characters.

Streaming. `POST /api/chat/stream` runs the same agent loop but replies with `text/event-stream`. Each event is one line, `data: {"type": ..., "payload": ...}`, followed by a blank line:

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

Personalisation. Each student has a profile (semester, section, electives, interests) and academic records (attendance and grades per course). When a chat request starts, the profile is loaded with the student, and the assistant's context says who they are: name, year, branch, current semester, electives and interests. Interests are editable on the profile page; the rest comes from the student record. The data is demo data, generated by `data/generate_academic_data.py` (see [`data/README.md`](../data/README.md)).

Notifications and background jobs. A student can allow web push notifications in their browser (profile page); the server then keeps that browser's address and keys (`push_subscriptions`) and sends messages with `pywebpush`. Students are told when a registration is confirmed, when a waitlist seat opens for them (a cancellation, or an admin raising the capacity, registers the first students waiting), when a new event matches a category they said they like (sent in the background right after the event is created), and by two scheduled jobs: a reminder for each registered event starting within the next 24 hours (every day at 08:00) and a warning for attendance below 75% (Mondays at 09:00), both in Asia/Kolkata time and only for students with a subscribed browser. Push is off until `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY` and `VAPID_SUBJECT` are set (`make vapid-keys` makes the key pair). Because the server sends a request to whatever address a browser registers, only the addresses of the Google, Mozilla, Apple and Windows push services are accepted, when saved and again when sending; anything else is refused or dropped. A push service that says a browser is gone (404 or 410) has its row deleted. The two jobs run in Celery (`app/worker.py`: `celery -A app.worker:celery_app worker` and `... beat`), which `docker-compose.yml` starts as `celery-worker` and `celery-beat`; run exactly one beat, or every job runs twice. A reminder is not remembered, so running the job twice sends it twice. Not done: exam schedule updates (the app has no way to change the exam schedule), and email notifications, which were dropped.

Security.
- Rate limits (slowapi): the chat is limited per signed-in student (`RATE_LIMIT_CHAT`, default `30/minute`, one allowance shared by `/api/chat` and `/api/chat/stream`), and sign-in, sign-up and wrong admin keys per visitor address (`RATE_LIMIT_AUTH`, `10/minute`), which also closes the earlier gap of unlimited password guessing. A refusal is `429 rate_limited` with `Retry-After`. Counters live in Redis when `REDIS_URL` is set (needed with more than one process: otherwise each process allows the full limit) and in memory otherwise. Behind a proxy the visitor's address comes from `X-Forwarded-For`, which uvicorn trusts only from addresses in `FORWARDED_ALLOW_IPS`; `docker-compose.prod.yml` sets it to `*` because only Caddy can reach the backend, and a real run showed the visitor's address, not Caddy's, being counted.
- Cleaning and screening messages (`app/security/guard.py`): every chat message is first cleaned (Unicode normalised so look-alike letters read as themselves, zero-width, bidirectional and control characters removed, blank runs collapsed; ordinary text in any language is untouched), then scored against weighted patterns for taking over an assistant (ignore your instructions, reveal your prompt, role changes and jailbreak terms, fake system delimiters, other students' records, sending data to a URL, image-link exfiltration, encoded blobs). One weak signal is noted, a clear attack (score 3 or more) is refused with a polite fixed reply, never reaches the model, and is not saved, so it cannot come back through the history. `PROMPT_GUARD=block|log|off` (log mode lets messages through and counts them, for tuning). The log records which rules matched, never the message. This is a heuristic, not a guarantee: anyone can rephrase around a pattern list, and it may refuse an innocent message. What actually limits the damage is that the assistant acts only for the signed-in student, tools never take a student id from the model, and every change needs the student's approval. The system prompt and the retrieved-passage block also tell the model to treat such content as data. A model-based classifier (Groq lists Llama Prompt Guard 2 as a preview model) could be added behind the same function, at the cost of a call per message.
- Admin API keys: scripts can call admin endpoints with an `X-Admin-Key` header instead of a session. `python -m app.cli create-admin-key` prints a key once and its SHA-256 digest; only digests go in `ADMIN_API_KEY_HASHES`. A key is an administrator (never a student), is compared in constant time, is rate limited, and is logged only as the first eight characters of its digest.
- HTTPS: Caddy terminates TLS and renews its certificate (`docker-compose.prod.yml`). The backend redirects any request the proxy saw as HTTP, sends HSTS in production, and adds `nosniff`, frame denial, a referrer policy and (for `/api`) a `default-src 'none'` content security policy; sign-in answers are `no-store`. The frontend sets the same basic headers; it has no content security policy yet.
- Settings checked at start: with `ENVIRONMENT=production` the application refuses to start unless `CORS_ORIGINS` are `https://host` origins (no `*`, no path), `COOKIE_SECURE=true`, and `JWT_SECRET` is set. In every environment a malformed origin such as `http:/localhost:3000` (one slash) is warned about.
- API documentation: the interactive pages (`/docs`, `/redoc`) and the schema (`/openapi.json`) list every endpoint, including the admin ones, so they are off when `ENVIRONMENT=production`.
- Secrets from files: `GROQ_API_KEY`, `OPENAI_API_KEY`, `JWT_SECRET`, `SMTP_PASSWORD`, `DATABASE_URL` and `ADMIN_API_KEY_HASHES` and `VAPID_PRIVATE_KEY` can each be given as `NAME_FILE=/path`, which is how Docker, Kubernetes and Vault Agent hand secrets over without putting them in the environment. The file wins over the variable. Rotating means replacing the file and recreating the container (the secrets are read once at start). No Vault client is built in. In `docker-compose.prod.yml` the files live in `./secrets` (git-ignored) and are mounted with `:z` for SELinux hosts; they must be readable by the container's user (uid 1000).
- All of it was run for real: HTTPS through Caddy, the redirect, HSTS, secure cookies, `/metrics` not reachable from outside, an injection attempt refused, an admin key accepted and a wrong one refused, and the eleventh login in a minute answered 429 with the counters visible in Redis. That run found that the container entrypoint ignored `JWT_SECRET_FILE`, and that Docker secrets are unreadable under SELinux, both fixed.

Tests. `pip install -r requirements-dev.txt`, then `pytest` (about 1,100 tests in a minute; the slow real-model evaluation is `pytest -m slow`). `pytest --cov=app` reports coverage: 98% when measured, and CI fails below 90%. `tests/test_endpoints_async.py` calls every endpoint over HTTP with `httpx.AsyncClient` as a signed-out visitor and as each of the four roles, against an access table that must list every operation in the OpenAPI schema, so an endpoint cannot be added without saying who may use it, and a weakened permission fails the test. The frontend has component tests (Vitest and Testing Library): `cd frontend && npm test`.

**Observability (`app/observability/`).**
- Logs are one JSON object per line (`LOG_FORMAT=console` for readable text, `LOG_LEVEL`), written with structlog; the libraries' own logs go through it too. Each request gets an id (a sensible `X-Request-ID` from the caller is kept, otherwise one is made), returned in the response and added to every line logged while it is handled, along with the signed-in user's id and role and the trace id. One `request` line per request has the method, path, status and duration; a streamed reply is timed to its last chunk. The agent logs its decisions (`rag.retrieve`, `agent.reason` with the tier and the tools asked for, `agent.route`, `agent.confirmation`) and each tool call (`agent.tool`: name, outcome and duration, never the arguments or results, which hold personal data) and each model request (`llm.request`). Passwords, cookies and message text are not logged (tests check).
- Metrics are served at `/metrics`: request counts and latency per route (prometheus-fastapi-instrumentator) plus `agent_tool_rounds_total`, `agent_tool_calls_total{tool,status}`, `agent_tool_duration_seconds`, `agent_confirmations_requested_total`, `rag_retrieval_latency_seconds`, `rag_chunks_returned_count`, `llm_requests_total`, `llm_request_duration_seconds` and `llm_tokens_used_total`. Tool names the model invents are counted as `unknown` so they cannot create unlimited series. Tokens are counted only when the service reports usage while streaming (OpenAI and Ollama do; Groq documents nothing for it). `/metrics` is not served by the production reverse proxy, so it is reachable only inside the network. Metrics are per process: with several uvicorn workers each would need scraping.
- Monitoring stack: `docker compose --profile monitoring up -d` adds Prometheus, Grafana (http://localhost:3001, user `admin`, password `GRAFANA_PASSWORD`, with a provisioned "Campus Copilot" dashboard of twelve panels) and Jaeger (http://localhost:16686). SELinux hosts need the `:z` mount labels already in the compose files.
- Tracing: with `OTEL_EXPORTER_OTLP_ENDPOINT` set (for example `http://jaeger:4318`), every request and every database query becomes a span of one trace, and log lines carry the trace id. The OpenTelemetry SQLAlchemy package declares support only up to SQLAlchemy 2.0 and refuses to start on the 2.1 used here unless its dependency check is skipped; it works through event hooks that 2.1 still has, a test checks that a query produces a span, and queries were seen arriving in Jaeger from Postgres.
- Sentry: with `SENTRY_DSN` set, unexpected errors are reported. Expected failures (`AppError`) are not, and no cookies, headers, bodies, query strings or stack-frame variables are sent. That last one matters: the variables in a traceback's frames include the request itself, with its cookie, and a test found exactly that leak in the first version. The frontend reports browser and server rendering errors with `NEXT_PUBLIC_SENTRY_DSN` / `SENTRY_DSN`; its v11 SDK collects cookies, headers and bodies by default (v10 did not), so `frontend/lib/sentryOptions.ts` switches every category off, and a real browser test checked that a reported error carried neither the cookie nor the query string.

Running in containers. `backend/Dockerfile` is multi-stage (the dependencies are installed in a builder stage and only the virtual environment is copied into a slim runtime image) and runs as an unprivileged user. It must be built from the repository root, because the app reads `data/` and `knowledge/` beside `backend/`. The entrypoint applies the migrations and loads demo data into empty tables, and refuses to start without `JWT_SECRET`; set `RUN_MIGRATIONS=false` when several copies start at once and run `alembic upgrade head` once instead. State lives on two volumes: `/var/lib/campus` (SQLite file if used, Chroma files, uploads) and `/home/app/.cache` (the downloaded search models). `requirements.txt` is what runs; `requirements-dev.txt` adds the test tools. The stack was built and started for real, on Postgres, with every migration applied and the knowledge base ingested: building it found that `qdrant-client` had never been listed in `requirements.txt`, which is fixed.

**Choosing the language model (`app/llm/`).** The agent never talks to a provider directly. `BaseLLMClient` is what it needs: `stream_completion()` (a provider implements this), and `chat_completion()` and `tool_call()` built on it. Failures come out as the application's own `AppError`, whichever service failed. Groq, OpenAI and Ollama all speak the OpenAI chat protocol, so one `OpenAICompatibleClient` serves all three through their SDKs (`GroqLLMClient`, `OpenAILLMClient`, `OllamaLLMClient` only choose the SDK object, the models, and whether to ask for token usage while streaming). Switch with `LLM_PROVIDER=groq|openai|ollama`.

- Groq has defaults, current as of Groq's models page in October 2026: `openai/gpt-oss-20b` for *fast* and `openai/gpt-oss-120b` for *balanced* and *best* (no larger production model exists there). The roadmap's `llama-3.1-8b-instant` and `llama-3.3-70b-versatile` were scheduled to shut down for free and developer accounts on 2026-08-16, so they are not used. `GROQ_MODEL` still works as the old name for `LLM_MODEL`.
- Ollama (fully local, no API cost, works offline) and OpenAI have no default model, and `LLM_MODEL` is required: which models exist and handle tool calls depends on what you have pulled or may use. `OLLAMA_BASE_URL` defaults to `http://localhost:11434/v1`; `OPENAI_BASE_URL` points the OpenAI client at any compatible server (then no key is needed). The `tool_choice` field is never sent, because Ollama rejects it and the default is the same.
- Quality tiers. `POST /api/chat` takes an optional `quality`: `fast`, `balanced` or `best`. Left out, ordinary questions use *balanced* and a multi-step task (a plan, or a follow-up round after tools ran) uses *best*; the router always uses *fast*. Each tier's model is `LLM_MODEL_FAST`, `LLM_MODEL` and `LLM_MODEL_BEST`; an unset tier falls back to `LLM_MODEL`.
- Not verified: nothing here has run against a live Groq, OpenAI or Ollama server. Token usage while streaming is requested from OpenAI and Ollama (`stream_options.include_usage`, which Ollama documents) but Groq documents nothing for it, so it is read if present and ignored if not.

**Choosing the embedding model (`app/rag/embeddings.py`).** `BaseEmbeddingFunction` turns text into vectors for both Chroma and Qdrant. `EMBEDDING_PROVIDER=local` (default) is `all-MiniLM-L6-v2` on the ONNX runtime (the roadmap names it under sentence-transformers; Chroma's bundled ONNX build is the same model without PyTorch, and a knowledge base built earlier opens unchanged); `ollama` defaults to `nomic-embed-text`, `openai` to `text-embedding-3-small`, either overridable with `EMBEDDING_MODEL`. Vectors from different models cannot be compared, so the model's identity is stored with every document: if it changes, ingest and search refuse to mix them (search degrades to "knowledge unavailable", the admin API answers `409 embedding_settings_changed`) until you run `python -m app.rag.ingest --full`, which drops the old collection first.

Analytics. After each answered question a `usage_events` row records which words it used (common words dropped), which tools ran, which documents were cited and whether any passage was retrieved: counts and names only, never the question or the answer, so it survives a student deleting their conversation without keeping what they wrote. `GET /api/admin/analytics` summarises these with the pending-action table. A word appears on the dashboard only once at least two questions used it, so a name or id typed once never shows. Two figures the roadmap asks for are not available and are reported as `null` with a note: the average retrieval distance (the reranker's score is not kept) and a cache hit rate (there is no answer cache). "Tool rounds per query" is reported as tool calls per reply. Events are only recorded from this version on, there is no backfill, and a question whose answer failed is not counted.

Conversation memory. A chat remembers what it has been about, so a follow-up like "register me for it" knows what "it" is. After each exchange the events, courses and faculty members mentioned (by the student or the assistant) are recorded for that conversation, and the most recent few of each kind are shown to the model at the start of the next turn, with the ids it needs for a tool call. Finding them takes no model call: events are matched against the events table (by id, name, or the part of the name before a colon), courses against the catalogue (by code, or by name for the student's own department only, since a name like "Machine Learning" is taught by two departments), and faculty against the names in the knowledge documents. So it is instant, and it can only find things that exist. Memory belongs to one conversation, is deleted with it, and a failure while recording it never fails the chat. `GET /api/chat/sessions/{id}/summary` asks the model for a short summary of one of the student's conversations; it is saved on the session and only written again once the conversation has grown. The model sees the conversation's most recent 60 messages, each cut to 600 characters.

Sessions. The server, not the browser, remembers the conversation. A student's first `POST /api/chat` creates a row in `sessions`, owned by that student, and sets a random `session_id` in an HttpOnly, `SameSite=Lax` cookie (HttpOnly means page scripts cannot read it) that remembers which conversation the browser is in. Each later request loads the session's most recent 40 messages (`HISTORY_WINDOW` in `api/chat.py`) and passes them to the agent; the reply is saved with its tool activity and sources. A failed agent run saves nothing. A session id that belongs to another student is treated as unknown, so nobody can read or continue someone else's conversation by guessing or borrowing an id. Set `COOKIE_SECURE=true` once the app is served over HTTPS.

Authentication. Students sign up with their USN, their name as it appears in the `students` roster, an email and a password, so an account can only be created for a real student record. Passwords are hashed with Argon2id (`pwdlib`; OWASP's preferred algorithm), and a login for an unknown email costs the same time as one for a known email and gives the same error, so neither timing nor wording reveals which accounts exist. A login sets two HttpOnly cookies: a short-lived (15 minute) signed JWT access token, and a random refresh token (14 days, only sent to `/api/auth/*`, only its hash is stored). Every refresh replaces the refresh token; presenting one that was already used (a sign of theft) revokes that whole login, apart from a 10 second grace for two tabs refreshing at once. The JWT algorithm is pinned, so unsigned or re-signed tokens are rejected. Because cookies authenticate requests, state-changing requests that carry an `Origin` header from an unknown site are refused (`OriginCheckMiddleware`), on top of `SameSite` cookies.

Roles. Every account has one role: `student`, `faculty`, `staff` or `admin`. Students are linked to a roster record; the others never are (a database `CHECK` enforces both). Public sign-up only ever makes students. Because anyone able to choose their own role could make themselves an admin, faculty, staff and admin accounts are created from the server with a command that prompts for the password (it is never an argument, so it stays out of shell history):

```bash
python -m app.cli create-user --role admin --name "Root Admin" --email root@campus.example
python -m app.cli create-user --role faculty --name "Dr. Rao" --email rao@campus.example \
    --department "Information Science and Engineering" --office B-204 --office-hours "Tue 2-4"
```

What each role may do: students chat, register themselves for events, and read events; staff also view and export all registrations; faculty also create events and edit their own department's (an event's `department` is set from the faculty member's, and cannot be changed by them; events with no department, including the seed events, are admin-only); admins can do everything staff and faculty can. Permissions are checked by the `require_roles(...)` dependency in `api/deps.py`. The CSV export prefixes any cell that starts with `=`, `+`, `-`, `@`, a tab or a line break with a single quote, so a hostile name cannot run as a spreadsheet formula ([OWASP: CSV injection](https://owasp.org/www-community/attacks/CSV_Injection)).

Managing the knowledge base. Admins can update what the assistant knows without touching the server. The curated corpus in `knowledge/` stays under version control; documents added through the API are kept apart in `backend/knowledge_uploads/` (gitignored, `KNOWLEDGE_UPLOAD_DIR`) and are searched along with it. An upload is a `.md` file, or a `.pdf` whose text is read with `pypdf` and stored as markdown with a section per page (a scanned PDF has no text and is refused; password-protected ones too); uploading a name again replaces the earlier one. File names are restricted to letters, digits, spaces, dots, dashes and underscores with no folders, the size limit is 10 MB, an upload cannot replace a curated document, and curated documents cannot be deleted through the API (change the file in the repository and ingest again). Only one ingest runs at a time. The evaluation takes about a minute, so `POST /api/admin/rag/eval` starts it in the background and `GET` returns `idle`, `running`, `done` (with the report) or `failed`; the state belongs to one server process, so with several workers ask the one that started it.

Known limits, until later roadmap phases: there is no email verification, so anyone who knows a student's USN and name can create that student's account first. Set `JWT_SECRET` (`openssl rand -hex 32`) in production. If it is unset the server makes a temporary one, which signs everyone out on every restart.

---

## Getting Started

Setup, with Docker or by hand, is in the [getting started guide](../docs/getting-started.md). This section keeps what is specific to the backend.

### Environment variables

| Variable | Default | Purpose |
| --- | --- | --- |
| `GROQ_API_KEY` | *(required)* | Your Groq API key |
| `GROQ_MODEL` | `openai/gpt-oss-120b` | Chosen for tool-use/reasoning support -- verify against `GET https://api.groq.com/openai/v1/models` before changing; Groq deprecates models over time and the docs' example model may not match what your account actually has |
| `CORS_ORIGINS` | `http://localhost:3000` | Comma-separated origins allowed to call this API |
| `DATABASE_URL` | `sqlite:///<repo>/backend/campus.db` | SQLAlchemy URL. Use `postgresql+psycopg://user:password@host:5432/dbname` for PostgreSQL |
| `JWT_SECRET` | *(random per start)* | Signs access tokens; at least 32 characters. Set it in production, otherwise every restart signs everyone out |
| `LLM_PROVIDER` | `groq` | `groq`, `openai` or `ollama` |
| `LLM_MODEL`, `LLM_MODEL_FAST`, `LLM_MODEL_BEST` | Groq: `openai/gpt-oss-120b`, `-20b`, same as balanced | The model per quality tier; `LLM_MODEL` is required for `openai` and `ollama` |
| `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `OLLAMA_BASE_URL` | *(unset)*, *(unset)*, `http://localhost:11434/v1` | Credentials and addresses for those providers |
| `EMBEDDING_PROVIDER`, `EMBEDDING_MODEL` | `local`, *(provider default)* | The embedding model; changing it needs `python -m app.rag.ingest --full` |
| `LOG_FORMAT`, `LOG_LEVEL`, `ENVIRONMENT` | `json`, `INFO`, `development` | Log style and level; `production` is set by `docker-compose.prod.yml` |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | *(unset)* | Send traces to this OpenTelemetry collector |
| `SENTRY_DSN`, `SENTRY_TRACES_SAMPLE_RATE`, `SENTRY_RELEASE` | *(unset)*, `0`, *(unset)* | Report unexpected errors to Sentry |
| `RATE_LIMIT_CHAT`, `RATE_LIMIT_AUTH`, `REDIS_URL` | `30/minute`, `10/minute`, *(memory)* | Request limits and where their counters live |
| `PROMPT_GUARD` | `block` | `block`, `log` or `off` for the message screen |
| `ADMIN_API_KEY_HASHES` | *(unset)* | SHA-256 digests of the keys that may use `X-Admin-Key` |
| `*_FILE` | | `GROQ_API_KEY_FILE`, `JWT_SECRET_FILE` and so on: read that secret from a file |
| `MULTI_AGENT` | `false` | Route each question to a specialist agent that sees only its own tools (adds a model call per question; unproven, so off) |
| `AGENT_PLANNING` | `false` | Plan multi-step requests before answering (adds a model call per question; unproven, so off) |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`, `SMTP_STARTTLS` | *(unset)*, `587`, ..., `true` | Outgoing email. With `SMTP_HOST` unset nothing is sent (the app logs it and carries on). With a login, STARTTLS encrypts the connection before the password is sent |
| `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`, `VAPID_SUBJECT` | *(unset)* | Web push notifications. All three are needed; with any missing, push is off. `make vapid-keys` makes the key pair, and the subject is a contact such as `mailto:admin@college.edu` |
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

## Notes for Contributors

- Keep HTTP routes in `api/` thin -- business logic belongs in `services/`, `rag/`, or `agent/`, so it can be reused and tested without spinning up a server.
- Any new tool the model should be able to call directly needs a schema in `tool_registry.TOOL_SCHEMAS` and an entry in `TOOL_FUNCTIONS`. If it mutates data, think hard about whether it belongs in `TOOL_FUNCTIONS` at all, or whether it should be an action in `actions/`, which waits for the student's approval.
- `data/events.json`, `data/students.json`, and `data/registrations.json` live at the repo root and are seed data only: `python -m app.db.seed` loads them into the database, and the app never reads or writes them at runtime. Changing the schema means editing `app/db/models.py` and generating a migration.

