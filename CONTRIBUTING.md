# Contributing to Campus Copilot

Thanks for taking an interest in the project. Campus Copilot is a workshop artifact first and a production system second — contributions are welcome, but should keep that goal in mind.

## Before You Start

For anything beyond a small fix (typo, dead link, obvious bug), open an issue first to discuss the direction. This project deliberately keeps its scope small — see the [Future Extensions](README.md#-future-extensions) section of the root README for ideas that are intentionally *out* of scope for now.

## What a Good Contribution Looks Like

A useful contribution should improve one of the following:

- User experience
- Retrieval quality
- Agent reliability
- Tool design
- Campus knowledge coverage
- Error handling
- Developer experience
- Documentation

## Where Things Live

The project is split into four independently-documented pieces. Read the relevant one before changing it:

- [`frontend/README.md`](frontend/README.md) — Next.js UI, design system, component layout.
- [`backend/README.md`](backend/README.md) — FastAPI service, RAG pipeline, agent loop, tools.
- [`knowledge/README.md`](knowledge/README.md) — the campus knowledge corpus (RAG source).
- [`data/README.md`](data/README.md) — structured application data (events, students, registrations).

## Ground Rules

- **Keep the system understandable.** Every component should have one obvious responsibility — see [Design Principles](README.md#-design-principles) in the root README.
- **Don't overbuild.** This project prefers a small, well-understood tool set over a large one. If you're adding a new tool the model can call, think about whether it needs the same human-confirmation treatment as `register_for_event` (see [Human-in-the-Loop](README.md#-human-in-the-loop)).
- **Keep the demo corpus fictional.** Documents in `knowledge/` and records in `data/` must stay clearly fictionalized workshop data — no real institution names, no real people, no real contact details.
- **Update docs alongside code.** If a change affects setup, the API contract, or the corpus structure, update the relevant README in the same change.

## Submitting a Change

1. Fork the repository and create a branch for your change.
2. Make the change, keeping it scoped to one concern.
3. Update the relevant README(s) if behavior, setup, or structure changed.
4. Open a pull request describing what changed and why.

## Reporting Issues

When filing an issue, include what you expected, what happened instead, and enough detail (steps, environment, relevant logs) for someone else to reproduce it.
