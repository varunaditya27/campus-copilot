# Campus Copilot Knowledge Corpus

This directory contains the curated knowledge corpus used by Campus Copilot for retrieval-augmented generation (RAG).

## Important

The documents are **demonstration data for the workshop**. They are intentionally written to resemble a realistic engineering-college campus knowledge base, but they are not an authoritative representation of any institution's current rules, policies, schedules, fees, or contact information.

For a real deployment, replace these documents with verified institutional material and attach source metadata, publication dates, and document versions.

## Corpus Design

The corpus is deliberately organized into topical documents rather than one enormous handbook. This makes the RAG pipeline easier to inspect and teaches an important production principle: retrieval quality depends heavily on the quality and structure of the source material.

```text
knowledge/
├── academics/
│   ├── attendance-and-academic-standing.md
│   ├── examinations-and-evaluation.md
│   ├── academic-calendar.md
│   └── academic-support.md
├── campus/
│   ├── library.md
│   ├── facilities.md
│   ├── departments-and-programs.md
│   └── campus-services.md
├── student-life/
│   ├── clubs-and-communities.md
│   ├── scholarships-and-financial-support.md
│   └── student-wellbeing.md
├── policies/
│   └── digital-conduct-and-computing.md
└── faq/
    └── common-student-questions.md
```

## Retrieval Expectations

The corpus should support questions that require:

- direct fact retrieval;
- combining information from multiple sections;
- comparing policies;
- finding procedural steps;
- identifying relevant campus services;
- answering follow-up questions using conversation context.

The agent should cite the document names used to construct an answer wherever possible.
