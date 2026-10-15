# Campus Copilot — Production Roadmap TODO

> Every item here is a concrete, shippable unit of work. Checked items are done. Everything else is the roadmap.
> Organized by phase. Within each phase, items are roughly ordered by dependency — complete top-to-bottom.

---

## Phase 0 — Already Shipped ✅

- [x] Next.js chat interface with agent activity log, source cards, and confirmation UI
- [x] FastAPI backend with structured request/response schemas
- [x] Groq LLM integration with tool-calling support
- [x] Chroma vector store (in-process, persistent)
- [x] RAG pipeline: markdown ingestion → section chunking → embedding → retrieval with distance threshold
- [x] Tool registry: `search_events`, `check_event_availability`, `calculate_attendance`, `register_for_event`
- [x] Human-in-the-loop registration confirmation gate
- [x] Multi-step agentic loop (up to 4 tool rounds)
- [x] Campus knowledge corpus (academics, administration, campus life, policies, FAQ)
- [x] Structured data layer: `events.json`, `students.json`, `registrations.json`
- [x] Events browser page (`/events`)
- [x] About page (`/about`)

---

## Phase 1 — Critical Foundations

> These are blocking issues. Nothing scales until these are done.

### 1.1 Database Migration

- [x] Replace `events.json`, `students.json`, `registrations.json` with SQLAlchemy models
- [x] Set up SQLite for local dev (zero infrastructure change, ACID-safe)
- [x] Write Alembic migrations for all tables: `students`, `events`, `registrations`, `sessions`, `users`
- [x] Replace all direct JSON file reads/writes in `event_service.py` and `registration_service.py` with DB queries
- [x] Add unique constraint on `(student_id, event_id)` for registrations
- [x] Add `docker-compose.yml` with a PostgreSQL service for production mode
- [x] Make the app switch between SQLite (dev) and PostgreSQL (prod) via `DATABASE_URL` env var

### 1.2 Streaming Responses

- [x] Convert `run_agent()` in `agent.py` to an async generator (done as a sync generator, `run_agent_stream()`: the Groq client and the database are synchronous, and Starlette runs a sync generator in a worker thread)
- [x] Add a `/chat/stream` SSE endpoint in FastAPI using `StreamingResponse`
- [x] Define a typed event protocol: `{ type: "tool_start" | "tool_done" | "rag_context" | "token" | "done", payload: ... }` (plus `reset` and `error`)
- [x] Update Next.js frontend to consume SSE stream with `EventSource` or `fetch` with `ReadableStream`
- [x] Show live token streaming in the chat bubble as the LLM generates
- [x] Show tool activity cards appear in real-time as each tool completes, not all at once at the end
- [x] Show a "thinking" skeleton state while the first tool round fires

### 1.3 Server-Side Session & Conversation History

- [x] Add a `sessions` table: `session_id (UUID)`, `student_id`, `created_at`, `updated_at`
- [x] Add a `messages` table: `id`, `session_id`, `role`, `content`, `tool_activity (JSON)`, `sources (JSON)`, `timestamp` (named `created_at`)
- [x] Generate a `session_id` cookie on first visit (or on login once auth exists)
- [x] Stop sending full `history[]` from client on every request — fetch history server-side using `session_id`
- [x] Expose `GET /chat/history?session_id=...` endpoint for frontend to load previous messages on refresh (reads the session cookie, which JavaScript cannot see, so no query parameter)
- [x] Add `GET /chat/sessions` to list all past sessions for a student
- [x] Add `DELETE /chat/sessions/{session_id}` to clear a conversation

### 1.4 Error Handling & Input Validation

- [x] Add Pydantic v2 validators on all tool function inputs (type coercion, field constraints)
- [x] Add structured FastAPI exception handlers: return `{ error_code, message, detail }` JSON on all 4xx/5xx
- [x] Catch and handle Groq API errors specifically: rate limit (429), context length exceeded, server error (500)
- [x] Catch and handle ChromaDB `RuntimeError` ("knowledge base not found") with a user-facing message instead of a 500
- [x] Add `MAX_DISTANCE` to config (currently hardcoded as `1.5` in `retriever.py`) and document its tuning
- [x] Validate `student_id` format on all registration-related endpoints
- [x] Add request size limits to FastAPI (guard against giant context payloads)

---

## Phase 2 — Authentication & Identity

### 2.1 Student Authentication

- [x] Add `POST /auth/register` — create a student account (USN, name, email, password hash)
- [x] Add `POST /auth/login` — return a signed JWT (access token + refresh token) (both set as HttpOnly cookies, not returned in the body)
- [x] Add `POST /auth/refresh` — rotate refresh token (with reuse detection)
- [x] Add `POST /auth/logout` — invalidate refresh token server-side
- [x] Add `GET /auth/me` — return the authenticated student's profile from the DB
- [x] Add FastAPI dependency `get_current_student` that validates JWT on protected routes
- [x] Store passwords with `bcrypt` (via `passlib`) (done with Argon2id via `pwdlib` instead: OWASP's preferred algorithm; `passlib` is not used)
- [x] Add NextAuth.js (or a custom auth context) on the frontend for session management (custom auth context, since the backend owns the session)
- [x] Protect all chat and registration endpoints behind JWT middleware
- [x] Auto-inject `student_id` from the JWT into agent context — students should never have to type their own ID

### 2.2 Role-Based Access Control

- [x] Add a `role` field to the user model: `student | faculty | staff | admin`
- [x] Create a `faculty` table linked to `users`: faculty_id, name, department, office, office_hours (the name lives on `users`, so it is not repeated)
- [x] Admin role can access all admin CRUD endpoints (the role check exists and is used by the endpoints built so far; the rest of phase 5 uses it)
- [x] Faculty role can create/edit events assigned to their department
- [x] Staff role can view all registrations and export them
- [x] Student role can only read and self-register

### 2.3 Institutional SSO (Stretch)

- [ ] Add SAML 2.0 / OAuth2 provider support for integration with institutional identity systems
- [ ] Accept signed USN-based tokens from a college portal if available
- [ ] Fall back to local password auth if SSO is unavailable

---

## Phase 3 — RAG Pipeline Upgrade

### 3.1 Better Chunking

- [x] Replace header-only splitting in `ingest.py` with a recursive character splitter (512-token chunks, 64-token overlap) (done as a heading-aware splitter with 256-token chunks and 32 overlap: the embedding model cuts off anything over 256 tokens, and 256 measured at least as well as the alternatives)
- [x] Preserve parent document metadata on every chunk (document name, section, page range if applicable)
- [x] Deduplicate identical chunks before inserting into Chroma
- [x] Support incremental ingestion: only re-embed files that have changed (track file hashes)
- [x] Add ingestion logging: report total chunks, skipped files, time taken

### 3.2 Hybrid Retrieval (BM25 + Semantic)

- [x] Add `rank-bm25` to `requirements.txt` (`bm25s` instead: `rank-bm25` has had no release since 2022)
- [x] Build a BM25 index over the knowledge corpus at ingest time, persist it alongside Chroma (built in memory from the store instead, in milliseconds, so it cannot disagree with the store)
- [x] At query time, run both BM25 and Chroma in parallel (run one after the other: the keyword search takes about a millisecond)
- [x] Fuse results using Reciprocal Rank Fusion (RRF)
- [x] Expose `k` and `rrf_k` as config parameters

### 3.3 Cross-Encoder Reranking

- [x] Add `sentence-transformers` to `requirements.txt` (`fastembed` instead: same model on ONNX Runtime, without PyTorch)
- [x] Load `cross-encoder/ms-marco-MiniLM-L-6-v2` as a local reranker model
- [x] After hybrid retrieval returns top-N candidates, rerank them with the cross-encoder
- [x] Return top-k reranked results to the LLM context (k=3 default, configurable)
- [x] Cache the reranker model in memory (only load once at startup)

### 3.4 Vector Store Upgrade

- [x] Migrate from in-process `chromadb.PersistentClient` to ChromaDB in HTTP server mode (optional: set `CHROMA_HOST`; local files stay the default)
- [x] Add `qdrant` as an alternative backend behind a `VECTOR_STORE=chroma|qdrant` env switch
- [x] Run the vector store as a separate Docker Compose service
- [x] Fix the `lru_cache` on `_get_collection()` — it breaks under multiple Uvicorn workers; replace with an app-lifespan singleton (replaced by a lock-guarded shared retriever that the app warms up at startup)

### 3.5 RAG Evaluation

- [x] Build a golden dataset: 50+ question/ground-truth-answer pairs from the knowledge corpus (92, plus off-topic and near-miss queries)
- [x] Write a `scripts/eval_rag.py` that runs each question through the retriever and scores Recall@3, MRR, and Hit Rate (`python -m app.rag.evaluate`)
- [x] Run this eval before and after any retriever change and log the delta
- [x] Add a `GET /admin/rag/eval` endpoint that triggers an eval run and returns a JSON report (`POST /api/admin/rag/eval` starts it in the background and `GET` returns the report, because a run takes about a minute)

### 3.6 Document Ingestion API

- [x] Add `POST /admin/knowledge/ingest` — trigger a full re-ingest of the `knowledge/` corpus (incremental by default, `?full=true` for a full rebuild)
- [x] Add `POST /admin/knowledge/upload` — accept a `.md` or `.pdf` file, parse and add to Chroma without a full rebuild
- [x] Add `GET /admin/knowledge/status` — return collection name, document count, last ingested timestamp
- [x] Add `DELETE /admin/knowledge/{document_name}` — remove a specific document's chunks from the collection (uploaded documents only; curated ones are managed in the repository)

---

## Phase 4 — Agent Architecture Overhaul

### 4.1 LangGraph Agent Migration

- [x] Add `langgraph` and `langchain-core` to `requirements.txt` (`langgraph` pulls in `langchain-core`)
- [x] Define a typed `AgentState` dataclass: `messages`, `tool_calls`, `rag_chunks`, `student_profile`, `pending_confirmation`, `loop_count`
- [x] Rebuild `run_agent()` as a LangGraph `StateGraph` with nodes: `retrieve`, `reason`, `execute_tools`, `request_confirmation`, `respond`
- [x] Add explicit edge conditions: `should_call_tools`, `is_confirmation_needed`, `is_done`
- [x] Replace the manual `for _ in range(MAX_TOOL_ROUNDS)` loop with LangGraph's cycle detection (LangGraph has no cycle detection; the loop is now a graph cycle bounded by `loop_count` in the state, with `recursion_limit` as a safety net)
- [x] Add a `plan` node that decomposes complex multi-step goals into an ordered sub-goal list before executing tools (built and tested, off by default: `AGENT_PLANNING`)
- [x] Enable parallel tool execution when multiple non-dependent tool calls are requested in the same round

### 4.2 Student Memory & Personalization

- [ ] Add a `student_profiles` table: `student_id`, `major`, `semester`, `branch`, `section`, `electives`, `preferences (JSON)`
- [ ] Add a `student_academic_records` table: `student_id`, `course_code`, `attended`, `total`, `grade`
- [ ] At the start of every agent run, fetch the authenticated student's profile from DB
- [ ] Inject the profile as a persona block in the system prompt: name, year, branch, current semester
- [ ] Add a `GET /students/me/profile` endpoint for the frontend to display profile info
- [ ] Add a `PUT /students/me/profile` endpoint to let students update their preferences
- [ ] Let the agent reference academic records to give personalized attendance/CGPA answers

### 4.3 Conversation Memory

- [ ] Implement a sliding-window context strategy: always include the last N messages from the session
- [ ] Add entity extraction on each turn: extract and store entities (event names, course codes, faculty names) mentioned in the conversation
- [ ] Let the agent reference extracted entities in follow-up turns without the user repeating them ("which event?" → agent already knows from context)
- [ ] Add a `GET /chat/sessions/{session_id}/summary` endpoint that uses the LLM to produce a 2–3 sentence summary of a past conversation

### 4.4 Tool Expansion — Academic

- [ ] `get_student_timetable(student_id, day?)` — return schedule for today or a given day
- [ ] `get_course_info(course_code)` — syllabus, credits, faculty, lab hours
- [ ] `get_faculty_profile(faculty_id_or_name)` — designation, department, office, office hours, email
- [ ] `get_exam_schedule(student_id, semester)` — upcoming exams, dates, rooms
- [ ] `get_cgpa(student_id)` — compute current CGPA from academic records
- [ ] `get_attendance_report(student_id)` — per-subject attendance, highlight subjects below threshold
- [ ] `get_elective_options(student_id)` — list available electives for the student's current semester and branch
- [ ] `get_fee_dues(student_id)` — outstanding fees, payment deadlines

### 4.5 Tool Expansion — Campus Operations

- [ ] `check_library_availability(title_or_isbn)` — book availability, shelf location, due dates
- [ ] `reserve_library_book(student_id, book_id)` — reserve a book (human-in-the-loop confirmation)
- [ ] `get_canteen_menu(day?)` — today's or a given day's canteen menu
- [ ] `book_study_room(student_id, room_id, date, time_slot)` — study room reservation (HITL)
- [ ] `report_maintenance_issue(location, description, category)` — submit a campus maintenance request
- [ ] `get_bus_schedule(route?)` — college shuttle timings and routes
- [ ] `get_lost_and_found(keyword)` — search lost and found registry
- [ ] `submit_lost_item(description, location_found)` — add to lost and found

### 4.6 Tool Expansion — Grievances & Support

- [ ] `create_grievance_ticket(student_id, category, description)` — raise a formal complaint (HITL confirmation)
- [ ] `get_grievance_status(ticket_id)` — check status of a previously submitted ticket
- [ ] `get_counselling_slots()` — list available student counselling appointment slots
- [ ] `book_counselling_appointment(student_id, slot_id)` — book appointment (HITL)
- [ ] `get_placement_drives(company?, date_range?)` — upcoming placement drives and eligibility criteria
- [ ] `check_placement_eligibility(student_id, company_id)` — check if a student meets criteria for a specific drive

### 4.7 Tool Expansion — Events (Enhanced)

- [ ] `get_event_detail(event_id)` — full event details including organiser, prerequisites, materials needed
- [ ] `get_my_registrations(student_id)` — list all events the student is registered for
- [ ] `cancel_event_registration(student_id, event_id)` — cancel a registration (HITL)
- [ ] `join_event_waitlist(student_id, event_id)` — join waitlist if event is full
- [ ] `get_event_feedback_form(event_id)` — return feedback form link or embedded form
- [ ] `submit_event_feedback(student_id, event_id, rating, comments)` — submit post-event feedback

### 4.8 Multi-Agent Architecture

- [ ] Define a `RouterAgent` that classifies incoming user intent into a domain: `academic | events | library | grievance | general`
- [ ] Create an `AcademicAgent` specialised for timetables, attendance, CGPA, and course queries
- [ ] Create an `EventsAgent` specialised for event discovery, registration, and waitlists
- [ ] Create a `LibraryAgent` specialised for book search, reservations, and due dates
- [ ] Create a `GrievanceAgent` specialised for ticket creation and status tracking
- [ ] Implement a LangGraph supervisor pattern: `RouterAgent` dispatches to the right specialist and collects the response
- [ ] Allow the router to dispatch to multiple agents in parallel for compound queries ("find me an event AND check my attendance")

---

## Phase 5 — Admin Dashboard

### 5.1 Event Management

- [ ] Add `POST /admin/events` — create a new event (name, description, date, time, venue, capacity, category, organiser)
- [ ] Add `PUT /admin/events/{event_id}` — update an event
- [ ] Add `DELETE /admin/events/{event_id}` — cancel/delete an event
- [ ] Add `GET /admin/events/{event_id}/registrations` — list all registrations for an event with student details
- [ ] Add `POST /admin/events/{event_id}/registrations/export` — export registration list as CSV
- [ ] Build `/admin/events` page in Next.js: table of all events, create/edit modal, delete confirmation
- [ ] Build `/admin/events/[id]` page: registration list, export button, capacity gauge

### 5.2 Student Management

- [ ] Add `GET /admin/students` — paginated list of all students with search/filter
- [ ] Add `GET /admin/students/{student_id}` — full profile with academic records, registrations, tickets
- [ ] Add `POST /admin/students/import` — bulk import students from a CSV file
- [ ] Build `/admin/students` page in Next.js: searchable table, click-through to student detail

### 5.3 Knowledge Management

- [ ] Build `/admin/knowledge` page: list all ingested documents with chunk counts and last-updated timestamps
- [ ] File upload UI for adding new markdown or PDF knowledge documents
- [ ] Trigger re-ingest from the UI with a progress indicator
- [ ] Preview a document's chunks and their embeddings metadata

### 5.4 Grievances Dashboard

- [ ] Add `GET /admin/grievances` — all tickets with filter by status (open / in-progress / resolved)
- [ ] Add `PUT /admin/grievances/{ticket_id}` — update status and add a resolution note
- [ ] Build `/admin/grievances` Kanban board: drag-and-drop tickets between status columns
- [ ] Send email notification to student when their ticket status changes

### 5.5 Analytics Dashboard

- [ ] Track: daily active users, messages per session, most-used tools, most-queried knowledge documents
- [ ] Build `/admin/analytics` page with charts: DAU graph, tool usage pie chart, top-10 queries word cloud
- [ ] Add agent performance metrics: average tool rounds per query, confirmation accept/reject rate
- [ ] Add RAG metrics: average retrieval distance, cache hit rate, queries that returned zero context

---

## Phase 6 — Notifications & Integrations

### 6.1 Email Notifications

- [ ] Add `email_service.py` backed by SMTP (or SendGrid/Resend for production)
- [ ] Send confirmation email on successful event registration
- [ ] Send reminder email 24 hours before a registered event
- [ ] Send notification email when a grievance ticket status changes
- [ ] Send waitlist promotion email when a spot opens up
- [ ] Admin can send bulk announcement emails to all registered students for an event

### 6.2 Push Notifications (Web Push)

- [ ] Add service worker to Next.js frontend for Web Push API
- [ ] Store push subscription objects per student in the DB
- [ ] Add `POST /notifications/subscribe` to register a student's push subscription
- [ ] Trigger push for: event reminders, registration confirmations, new events matching student interests, exam schedule updates

### 6.3 Calendar Integration

- [ ] Add `GET /students/me/calendar.ics` — export registered events as an `.ics` file (importable to Google Calendar, Apple Calendar)
- [ ] Add "Add to Calendar" button in the frontend confirmation card and registration list
- [ ] Add Google Calendar OAuth integration to directly push events into the student's Google Calendar (optional, HITL consent)

### 6.4 Proactive Agent (Scheduled Tasks)

- [ ] Add Celery + Redis to `docker-compose.yml` for async task queue
- [ ] Scheduled task (daily, 8 AM): scan all upcoming registered events in the next 24 hours → send reminders
- [ ] Scheduled task (weekly): detect students with attendance below 75% → send proactive warning with tool-generated summary
- [ ] Scheduled task (on event capacity change): promote students from waitlist automatically
- [ ] Scheduled task (on new event creation): match event category to student interests → send targeted notifications

---

## Phase 7 — Voice & Multimodal

### 7.1 Voice Interface

- [ ] Add `POST /voice/transcribe` — accept audio blob, run Whisper (local via `faster-whisper`) and return transcript
- [ ] Add voice input button in the chat UI — record audio, send to `/voice/transcribe`, auto-fill the chat input
- [ ] Add `POST /voice/synthesize` — accept text, return audio stream using a local TTS model (e.g., Kokoro, Piper)
- [ ] Play synthesized audio in the frontend after each agent response (user-toggleable)
- [ ] Add a full voice mode: hold-to-speak → auto-transcribe → agent responds → auto-speak response

### 7.2 Document Understanding (Multimodal RAG)

- [x] Add `POST /admin/knowledge/upload-pdf` — accept a PDF, extract text with `pymupdf`, chunk and embed (done through the general upload endpoint, using `pypdf`: PyMuPDF is AGPL-licensed)
- [ ] Add OCR fallback for scanned PDFs using `pytesseract` + image preprocessing
- [ ] Support ingesting lecture slide decks (`.pptx`) — extract slide text + titles
- [ ] Add `POST /chat/ask-document` — let a student upload a document (e.g., marksheet, question paper) and ask questions about it
- [ ] Store uploaded documents in object storage (MinIO for local / S3 for cloud)

### 7.3 Image Input

- [ ] Allow students to send an image in the chat (e.g., a photo of a timetable, a handwritten question)
- [ ] Route image inputs to a multimodal LLM (e.g., `llava` via Ollama, or Groq's vision endpoint)
- [ ] Extract structured data from timetable images and store in the student's profile

---

## Phase 8 — LLM Backend Flexibility

### 8.1 LLM Abstraction Layer

- [ ] Create a `BaseLLMClient` abstract class with methods: `chat_completion()`, `stream_completion()`, `tool_call()`
- [ ] Implement `GroqLLMClient` (current default)
- [ ] Implement `OllamaLLMClient` for fully local inference (no API cost, works offline)
- [ ] Implement `OpenAILLMClient` as a drop-in for OpenAI-compatible APIs
- [ ] Add `LLM_PROVIDER=groq|ollama|openai` env var to switch providers at runtime
- [ ] Add `LLM_MODEL` env var to configure which model to use per provider

### 8.2 Embedding Abstraction

- [ ] Create a `BaseEmbeddingFunction` interface
- [ ] Implement `SentenceTransformerEmbedding` (current: `all-MiniLM-L6-v2`)
- [ ] Implement `OllamaEmbedding` (e.g., `nomic-embed-text` via Ollama — fully local)
- [ ] Implement `OpenAIEmbedding` for `text-embedding-3-small`
- [ ] Add `EMBEDDING_PROVIDER` env var

### 8.3 Model Quality Tiers

- [ ] Define a `quality` request parameter: `fast | balanced | best`
- [ ] Map quality tiers to specific models per provider (e.g., fast = `llama-3.1-8b-instant`, best = `llama-3.3-70b-versatile` on Groq)
- [ ] Default to `balanced` for regular queries, `best` for multi-step agentic tasks

---

## Phase 9 — Infrastructure & DevOps

### 9.1 Containerization

- [ ] Write `docker-compose.yml` with services: `backend`, `frontend`, `postgres`, `redis`, `qdrant`, `celery-worker`, `celery-beat`
- [ ] Write `backend/Dockerfile` (multi-stage: builder + slim runtime)
- [ ] Write `frontend/Dockerfile` (Next.js standalone build)
- [ ] Add `.dockerignore` files to both services
- [ ] Add a `docker-compose.dev.yml` override for hot-reload development
- [ ] Add `Makefile` with targets: `make dev`, `make build`, `make test`, `make ingest`, `make migrate`

### 9.2 CI/CD Pipeline

- [ ] Add `.github/workflows/ci.yml`: on every PR, run backend `pytest`, frontend `tsc --noEmit`, ESLint
- [ ] Add `.github/workflows/build.yml`: on merge to `main`, build and push Docker images to GitHub Container Registry
- [ ] Add a `docker-compose.prod.yml` that pulls from GHCR instead of building locally
- [ ] Add GitHub Actions secret scanning check on every PR
- [ ] Add Dependabot config for Python and npm dependency updates

### 9.3 Observability

- [ ] Add `structlog` to backend for structured JSON logging on every request, agent decision, and tool call
- [ ] Add `prometheus-fastapi-instrumentator` — expose `/metrics` endpoint
- [ ] Add custom Prometheus metrics: `agent_tool_rounds_total`, `rag_retrieval_latency_seconds`, `rag_chunks_returned_count`, `llm_tokens_used_total`
- [ ] Add Grafana + Prometheus to `docker-compose.yml` for local monitoring
- [ ] Add distributed tracing with OpenTelemetry (instrument FastAPI + DB queries)
- [ ] Add Sentry SDK to both backend and frontend for error tracking in production

### 9.4 Testing

- [ ] Add `pytest` + `pytest-asyncio` to `requirements.txt`
- [x] Write unit tests for all tool functions (`search_events`, `calculate_attendance`, etc.)
- [x] Write unit tests for the RAG retriever (mock Chroma, test distance filtering)
- [ ] Write integration tests for all FastAPI endpoints using `httpx.AsyncClient`
- [x] Write end-to-end agent tests: send a message → assert the right tools are called → assert response structure
- [x] Write RAG eval tests that run the golden dataset and assert minimum Recall@3 threshold (`pytest -m slow`)
- [ ] Add `vitest` + `testing-library/react` for Next.js component tests
- [ ] Aim for >80% backend coverage; track with `pytest-cov`

### 9.5 Security

- [ ] Add rate limiting to the chat endpoint (e.g., 30 req/min per student) using `slowapi`
- [ ] Add CORS policy: restrict `allow_origins` to the deployed frontend URL in production
- [ ] Rotate GROQ_API_KEY using a secrets manager (HashiCorp Vault or GitHub Actions secrets)
- [ ] Add input sanitisation on all user-provided text before passing to the LLM (guard against prompt injection)
- [ ] Implement a prompt injection detection layer: classify incoming messages for adversarial patterns before routing to the agent
- [ ] Add HTTPS enforcement (reverse proxy with Nginx + Let's Encrypt or Caddy)
- [ ] Add API key authentication for the admin endpoints (separate from student JWT)

---

## Phase 10 — Mobile Application

### 10.1 Android App (Kotlin)

- [ ] Create a new Kotlin/Jetpack Compose project: `campus-copilot-android/`
- [ ] Implement a `ChatScreen` with real-time SSE consumption and streaming message rendering
- [ ] Implement `AgentActivityPanel` — expandable drawer showing tool activity in real-time
- [ ] Implement `ConfirmationBottomSheet` — native bottom sheet for registration confirmation
- [ ] Implement `EventsScreen` — scrollable event cards with filter chips
- [ ] Implement `ProfileScreen` — student info, registered events, attendance summary
- [ ] Add JWT auth: login screen + secure token storage in `EncryptedSharedPreferences`
- [ ] Add push notifications via Firebase Cloud Messaging (FCM)
- [ ] Add voice input via Android's `SpeechRecognizer` API with fallback to Whisper endpoint
- [ ] Add offline mode: cache last N conversation turns and knowledge snippets in Room DB

### 10.2 PWA (Progressive Web App)

- [ ] Add `next-pwa` to the Next.js frontend
- [ ] Configure service worker for offline caching of the shell, last conversation, and event list
- [ ] Add `manifest.json` with app name, icons, theme color
- [ ] Add "Add to Home Screen" prompt for mobile browsers
- [ ] Ensure the chat UI is fully responsive and thumb-friendly on 375px screens

---

## Phase 11 — Multi-Tenancy & Scaling

### 11.1 Multi-College Support

- [ ] Add a `tenants` table: `tenant_id`, `college_name`, `domain`, `logo_url`, `config (JSON)`
- [ ] Scope all DB queries by `tenant_id`
- [ ] Scope all Chroma/Qdrant queries by `tenant_id` (separate collections per tenant)
- [ ] Add tenant resolution by subdomain (`rvce.campuscopilot.app` → `tenant_id=rvce`)
- [ ] Add a tenant onboarding flow: upload knowledge corpus → auto-ingest → configure branding
- [ ] Add a super-admin role that can manage tenants

### 11.2 Horizontal Scaling

- [ ] Replace `lru_cache` singletons with Redis-backed caches for shared state across workers
- [ ] Move Chroma/Qdrant to a standalone server accessible by all backend replicas
- [ ] Move session storage to Redis (replace any in-memory state)
- [ ] Add a load balancer config (Nginx upstream block) for multiple backend replicas
- [ ] Test concurrent agent runs with k6 or Locust: target 100 concurrent users, <2s p95 latency

---

## Phase 12 — Research-Grade Enhancements

### 12.1 Agent Self-Evaluation

- [ ] After each agent response, run a lightweight LLM self-critique: "Was this answer grounded? Was it complete?"
- [ ] If critique score is below threshold, retry with a refined prompt (max 1 retry)
- [ ] Log self-critique scores to the analytics DB for long-term quality tracking

### 12.2 Knowledge Graph Integration

- [ ] Extract named entities from the knowledge corpus (faculty, courses, departments, policies) using `spaCy`
- [ ] Build a lightweight knowledge graph (NetworkX) linking entities: faculty → courses they teach, courses → departments, events → organiser
- [ ] At query time, augment the vector search with graph traversal: "who teaches OS?" → graph lookup → return faculty node
- [ ] Expose knowledge graph as a `GET /admin/knowledge/graph` JSON endpoint for visualisation

### 12.3 Feedback-Driven Continuous Improvement

- [ ] Add a thumbs-up / thumbs-down reaction to every chat message in the frontend
- [ ] Store feedback in a `message_feedback` table: `message_id`, `rating`, `comment`
- [ ] Expose `GET /admin/feedback` — paginated list of all feedback with message content
- [ ] Use negative-feedback messages as a curated set for RAG eval regression tests
- [ ] Periodically fine-tune the system prompt and retrieval parameters based on feedback patterns

### 12.4 Explainability

- [ ] Add a "Why did the agent say this?" button that shows: which RAG chunks were retrieved, which tools were called, which tool results influenced the response
- [ ] Show confidence indicators: if retrieval distance is high, label the response as "low confidence"
- [ ] Log full agent traces (all LLM messages, tool calls, tool results) to a `traces` table for debugging

---

## Backlog / Future Ideas

- [ ] Campus navigation: integrate a campus map and add a `get_directions(from, to)` tool that returns walking directions
- [ ] Peer study group matching: `find_study_partners(course_code)` — match students studying the same subject
- [ ] Alumni network integration: let students ask about career paths of alumni from their branch
- [ ] Smart timetable conflict detection: when registering for events, warn if they conflict with classes
- [ ] Automated question paper generation: faculty tool to generate practice questions from a course's knowledge docs
- [ ] AR campus tour: link location beacons to knowledge corpus sections for a location-aware campus guide
- [ ] Hackathon team finder: `find_hackathon_teammates(skills, event_id)` — match students by skill set
- [ ] Internship and job board integration: scrape or ingest college placement portal data into the knowledge corpus
- [ ] Mood-aware response tuning: brief sentiment detection on student messages → adjust response tone (stressed student gets calmer, more supportive phrasing)
- [ ] Multi-language support: detect query language → respond in the same language (Hindi, Kannada, Telugu) using multilingual LLMs

---

*Last updated: August 2026. This document is the authoritative roadmap. Update checkboxes as items are completed.*
