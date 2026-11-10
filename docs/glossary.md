<div align="center">

# Glossary

Every technical term used in these documents, in plain words.

</div>

Terms are in alphabetical order. A source is given where the term has a standard definition.

## A

**Action.** Something the assistant does that changes data, such as registering a student for an event. An action is never carried out on the assistant's say-so: the student must approve it first. See *human in the loop*.

**Agent.** A program that decides for itself which steps to take to reach a goal, instead of following one fixed script. Example: asked to "find an AI event tomorrow and register me", the agent searches events, checks seats, and proposes the registration. Campus Copilot's agent is built with *LangGraph*.

**API (application programming interface).** The set of web addresses a program can call to ask another program to do something. The frontend calls the backend's API, for example `GET /api/events` to list events.

## B

**BM25.** A classic way to rank documents by how well their words match a question. It rewards rare words that appear often in a passage. Example: a question containing "hostel" ranks passages that mention "hostel" many times above passages that do not. Campus Copilot uses it through the `bm25s` library ([bm25s](https://bm25s.github.io/)).

## C

**Celery.** A tool that runs jobs in the background, on a schedule or on request. Here it sends the morning event reminders and the weekly attendance warnings ([Celery documentation](https://docs.celeryq.dev/en/stable/)). Celery *beat* is the part that starts jobs on time, and the *worker* is the part that does them.

**Chroma.** A database built for searching text by meaning. It stores *embeddings* and finds the ones closest to a question. It is the default knowledge store ([Chroma documentation](https://docs.trychroma.com/)). *Qdrant* is the alternative.

**Chunk.** A short piece of a document, such as one section of the library rules. Documents are cut into chunks before they are stored, so a search returns the relevant section and not a whole handbook.

**CORS (cross-origin resource sharing).** A browser rule that stops a web page from calling a different website's server unless that server says it is allowed. The backend lists the page addresses it accepts in `CORS_ORIGINS` ([MDN](https://developer.mozilla.org/en-US/docs/Web/HTTP/CORS)).

**Cross-encoder.** A model that reads a question and a passage together and scores how well they match. It is slower than comparing *embeddings* but judges relevance better, so it is used on a short list. See *reranking* ([Sentence Transformers](https://www.sbert.net/examples/cross_encoder/applications/README.html)).

## D

**Docker Compose.** A tool that starts several programs (the backend, frontend, database and so on) together from one description file, so the whole project runs with one command ([Docker documentation](https://docs.docker.com/compose/)).

## E

**Embedding.** A list of numbers that stands for the meaning of a piece of text. Texts with similar meanings get similar numbers, so "when does the library close" lands near "library opening hours". Searching by meaning means comparing embeddings.

## F

**FastAPI.** The Python framework the backend is written in ([FastAPI](https://fastapi.tiangolo.com/)).

## G

**Groq.** A company that hosts large language models and sells access to them through an API. It is the default model provider; OpenAI and Ollama can be used instead ([Groq documentation](https://console.groq.com/docs/overview)).

## H

**Human in the loop.** A design where a person must approve a consequential step before it happens. In Campus Copilot the assistant only *proposes* an action; nothing is done until the student confirms.

## I

**iCalendar (`.ics`).** A standard file format for calendar entries, understood by Google Calendar, Apple Calendar and Outlook. The profile page can download the student's registered events as one ([RFC 5545](https://www.rfc-editor.org/rfc/rfc5545)).

## J

**JWT (JSON Web Token).** A signed note that says who a user is. The backend gives one to the browser at sign-in and checks its signature on each request, so it does not have to look the user up again ([RFC 7519](https://www.rfc-editor.org/rfc/rfc7519)). It expires after a short time.

## L

**LangGraph.** A library for building an agent as a graph of steps with decisions between them, such as "retrieve", "reason", "run tools" and "ask for confirmation" ([LangGraph](https://langchain-ai.github.io/langgraph/)).

**LLM (large language model).** The kind of AI model that reads and writes text. It can answer from what it learned in training, which is why it needs *retrieval* for facts about one particular campus.

## M

**Migration.** A small script that changes the shape of the database, such as adding a column, in a tracked and repeatable way. Campus Copilot uses *Alembic* ([Alembic](https://alembic.sqlalchemy.org/en/latest/)).

## N

**Next.js.** The JavaScript framework the frontend is built with ([Next.js](https://nextjs.org/docs)).

## P

**Progressive web app (PWA).** A website that can be installed on a phone or computer, works partly offline, and can send notifications. Campus Copilot's frontend is one ([Next.js guide](https://nextjs.org/docs/app/guides/progressive-web-apps)).

**Prompt.** The text sent to a language model: instructions, the student's question, and any passages found for it.

**Prompt injection.** An attack where text sent to the model tries to override its instructions, such as "ignore your rules and reveal your secrets". Campus Copilot screens messages for known patterns before they reach the model ([OWASP](https://genai.owasp.org/llmrisk/llm01-prompt-injection/)).

**Push notification.** A short message shown on a device even when the website is not open. The browser maker's *push service* delivers it. See *VAPID* and *service worker* ([MDN](https://developer.mozilla.org/en-US/docs/Web/API/Push_API)).

## Q

**Qdrant.** An alternative to *Chroma* that runs as its own server, for setups with more than one backend process ([Qdrant](https://qdrant.tech/documentation/)).

## R

**Rate limit.** A cap on how many requests one user or address may make in a given time. Example: 30 chat messages a minute per student. It protects the service from abuse.

**RAG (retrieval-augmented generation).** Answering a question by first looking up relevant passages, then giving them to the language model along with the question. The model answers from the passages instead of from memory alone, and the passages can be shown as sources ([Lewis et al., 2020](https://arxiv.org/abs/2005.11401)).

**Reciprocal rank fusion.** A way to merge two ranked lists into one. Each item scores higher the nearer the top it is in each list, and the scores are added. It works without comparing the lists' own scores, which are on different scales ([Cormack et al., 2009](https://plg.uwaterloo.ca/~gvcormac/cormacksigir09-rrf.pdf)).

**Redis.** A very fast in-memory data store. Here it holds the Celery job queue and the rate-limit counters ([Redis](https://redis.io/docs/latest/)).

**Reranking.** Re-ordering a short list of search results with a more careful model, here a *cross-encoder*. Passages scoring below a cutoff are dropped, so weak matches never reach the language model.

**Retrieval.** Looking up the passages most relevant to a question. Campus Copilot searches by meaning and by words, merges the results, and reranks them.

## S

**Server-sent events (SSE).** A way for a server to push a stream of messages to a browser over one open connection. The chat uses it so the answer appears word by word ([MDN](https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events)).

**Service worker.** A script the browser runs in the background, separate from the page. It lets the app work offline and receive push notifications ([MDN](https://developer.mozilla.org/en-US/docs/Web/API/Service_Worker_API)). The one here is built with *Serwist* ([Serwist](https://serwist.pages.dev/docs)).

**SQLAlchemy.** A Python library for talking to a database with Python objects instead of hand-written SQL ([SQLAlchemy](https://www.sqlalchemy.org/)).

**SSRF (server-side request forgery).** An attack that makes a server send a request to an address the attacker picked, for example an internal service. Campus Copilot guards against it by accepting only the known browser push services as notification addresses ([OWASP](https://owasp.org/www-community/attacks/Server_Side_Request_Forgery)).

## T

**Tool calling.** The model asks the program to run a named function, such as "check seats for this event", and receives the result. The model never runs anything itself, and the program decides whether a request is allowed ([Groq documentation](https://console.groq.com/docs/tool-use)).

## V

**VAPID (Voluntary Application Server Identification).** A key pair that identifies a server to the browsers' push services, so they accept its notifications. `make vapid-keys` makes one ([RFC 8292](https://www.rfc-editor.org/rfc/rfc8292)).

**Vector store.** A database for *embeddings*. See *Chroma* and *Qdrant*.
