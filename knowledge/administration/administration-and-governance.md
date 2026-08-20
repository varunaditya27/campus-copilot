# Administration and Governance

> **Demo corpus document:** Office names, titles, and reporting structures below are fictionalized workshop data.

## Purpose

This document gives Campus Copilot enough structural context to correctly point students toward the right office, without needing a live organizational directory. It answers "who handles this?" rather than "what is the policy?" — policy detail lives in the topic-specific documents elsewhere in the corpus.

## Institutional Structure

The demonstration campus is organized as follows:

```text
Office of the Principal / Director
        │
        ├── Dean of Academics
        │        └── Department Heads (per department)
        │                 └── Course Coordinators
        │
        ├── Dean of Student Affairs
        │        ├── Student Activity Centre
        │        ├── Hostel Administration
        │        └── Discipline and Grievance Committees
        │
        ├── Registrar's Office
        │        ├── Admissions
        │        ├── Examinations Cell
        │        └── Academic Records
        │
        └── Administrative Services
                 ├── Finance and Accounts
                 ├── IT Services
                 └── Facilities and Estate Management
```

## Office of the Principal / Director

The Principal or Director's office holds overall institutional responsibility and typically handles matters escalated beyond department or dean-level resolution.

## Dean of Academics

The Dean of Academics oversees curriculum, academic calendar coordination across departments, and cross-department academic policy. Department Heads report into this office for academic (as opposed to disciplinary or facilities) matters.

## Department Heads

Each engineering department (Information Science and Engineering, Computer Science and Engineering, Electronics and Communication Engineering, Electrical and Electronics Engineering, Mechanical Engineering) is led by a Head of Department (HOD), who oversees faculty allocation, department curriculum delivery, department-level student concerns, and department research direction. See [`faculty-and-departments-directory.md`](../campus/faculty-and-departments-directory.md) for representative faculty structure.

## Dean of Student Affairs

The Dean of Student Affairs office is the primary escalation point for non-academic student matters: hostel administration, student activity approvals, discipline, and grievance handling. Club and event approvals for larger campus-wide activities are typically routed through this office.

## Registrar's Office

The Registrar's Office is responsible for admissions administration, the examinations cell, and the official academic record system (transcripts, degree verification, semester registration records). Requests for an official document — a transcript, a bonafide certificate, a migration certificate — are Registrar's Office matters, not something Campus Copilot can produce.

## Administrative Services

Finance and Accounts handles fee collection, refunds, and scholarship disbursement logistics. IT Services maintains campus network, accounts, and computing infrastructure (see [`campus-services.md`](../campus/campus-services.md) for the student-facing IT Help Desk). Facilities and Estate Management maintains buildings, utilities, and campus infrastructure.

## Routing a Student Question

When a student's question implies an administrative action rather than a factual lookup, Campus Copilot should identify the responsible office from this document rather than guessing or fabricating a process. If no office is clearly implied by the corpus, the assistant should say so plainly rather than inventing one.
