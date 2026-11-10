<div align="center">

# Contributing

How to propose a change to Campus Copilot.

</div>

Thanks for taking an interest. Campus Copilot is a learning project and a reference implementation first, so contributions that keep it small and understandable are the most welcome.

## Before you start

For anything beyond a small fix (a typo, a dead link, an obvious bug), open an issue first to talk about the direction. The scope is kept small on purpose. The [roadmap](TODO.md) records what is done, what was decided against, and what is deferred.

## What a good contribution improves

- the experience of a student or an admin;
- retrieval quality or agent reliability;
- the design of a tool;
- the coverage of the campus documents;
- error handling and developer experience;
- the documentation.

## Where things live

Each part has its own document. Read the one for the part you are changing.

- [Architecture](docs/architecture.md): how the parts fit together.
- [Backend](backend/README.md): the API, the agent, retrieval, tools, security and settings.
- [Frontend](frontend/README.md): the screens, the design system and offline behaviour.
- [Knowledge](knowledge/README.md): the campus documents the assistant reads.
- [Data](data/README.md): the structured sample data.
- [Glossary](docs/glossary.md): technical terms in plain words.

## Ground rules

- Keep each part to one job. See the [principles](README.md#principles).
- Do not overbuild. A small, well-understood set of tools is preferred to a large one. If you add something the model can ask for that changes data, it must wait for the student's approval, like the existing actions (see [actions need a yes](docs/architecture.md#actions-need-a-yes)).
- Keep the sample data fictional. Documents in `knowledge/` and records in `data/` must not name a real institution, a real person or a real contact detail.
- Update the documents in the same change. If setup, the API or the corpus structure changes, change the matching document. A new technical term goes in the glossary.
- Draw diagrams as SVG files in `docs/diagrams/`, not as Mermaid or as text drawings.

## Before you open a pull request

```bash
make test
```

This runs the backend tests and the frontend type check, lint and tests. The same checks run on every pull request.

## Submitting a change

1. Fork the repository and make a branch.
2. Make the change, keeping it to one concern.
3. Update the documents if behaviour, setup or structure changed.
4. Open a pull request that says what changed and why.

## Reporting an issue

Say what you expected, what happened instead, and give enough detail (steps, environment, relevant logs) for someone else to reproduce it.
