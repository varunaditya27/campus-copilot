<div align="center">

# 📚 Campus Copilot — Knowledge Corpus

### The Virtual University the Agent Is Grounded In

**A markdown corpus simulating a complete engineering college — academics, administration, campus life, and policy — written so that retrieval quality reflects real source-document design, not toy data.**

<br />

[![Markdown](https://img.shields.io/badge/Markdown-000000?logo=markdown&logoColor=white)](https://www.markdownguide.org/)
[![Chroma](https://img.shields.io/badge/Chroma-5B21B6?logoColor=white)](https://www.trychroma.com/)

<br />

</div>

---

## ✨ What Lives Here

This is the retrieval source for [Campus Copilot](../README.md)'s RAG pipeline — the material the [backend](../backend/README.md) embeds into Chroma and the agent cites as `sources` when it answers a question. It is not application data: events, students, and registrations are structured JSON at the repo root and are queried through tools, not retrieval. This corpus is for the kind of knowledge that's genuinely document-shaped — policy, process, and "how does this place work" — the kind a real student would look up in a handbook rather than a database.

## Important

The documents are **demonstration data for the workshop**. They are intentionally written the way a real university actually writes its own material — as documents that assume they're being read by a student or staff member, not by an AI system — so that retrieval and citation quality reflect a real deployment rather than a corpus written with the RAG pipeline in mind. No individual document says "this is fictional"; that's stated once, here: no document names a real institution, and any name-like detail (faculty names, committee names) is a clearly invented placeholder for a fictional university.

For a real deployment, replace these documents with verified institutional material and attach source metadata, publication dates, and document versions.

---

## 🎓 Corpus Design

The corpus simulates a **complete virtual engineering university** rather than a handful of illustrative pages. The intent is to make retrieval meaningfully hard: many documents cover adjacent ground (a course grade dispute vs. a fee dispute vs. a ragging report all route through different committees), so the agent has to actually retrieve the right section, not just the right file.

Documents are organized into five topical categories rather than one enormous handbook. This is a production principle, not just tidiness: retrieval quality depends heavily on the structure of the source material, and a single sprawling document produces vague, low-precision chunks no matter how good the embedding model is.

```text
knowledge/
├── academics/
│   ├── curriculum-and-degree-structure.md
│   ├── grading-and-backlogs.md
│   ├── attendance-and-academic-standing.md
│   ├── examinations-and-evaluation.md
│   ├── academic-calendar.md
│   └── academic-support.md
│
├── administration/
│   ├── administration-and-governance.md
│   ├── admissions-and-fee-structure.md
│   └── placement-cell.md
│
├── campus/
│   ├── faculty-and-departments-directory.md
│   ├── departments-and-programs.md
│   ├── labs-and-research-centres.md
│   ├── library.md
│   ├── facilities.md
│   ├── hostel-and-accommodation.md
│   ├── health-and-medical-centre.md
│   ├── transportation-routes.md
│   ├── dining-and-transport.md
│   └── campus-services.md
│
├── student-life/
│   ├── clubs-and-communities.md
│   ├── fests-and-cultural-events.md
│   ├── sports-and-recreation.md
│   ├── research-and-projects.md
│   ├── career-development.md
│   ├── alumni-network.md
│   ├── international-and-exchange-programs.md
│   ├── scholarships-and-financial-support.md
│   └── student-wellbeing.md
│
├── policies/
│   ├── digital-conduct-and-computing.md
│   ├── code-of-conduct-and-discipline.md
│   └── anti-ragging-and-grievance-redressal.md
│
└── faq/
    └── common-student-questions.md
```

### Why This Split

- **academics/** — how the degree itself works: curriculum, grading, attendance, exams, calendar, and support.
- **administration/** — how the institution is run: governance structure, admissions/fees, placements. Distinct from `academics/` because these are institutional-process documents, not degree-content documents.
- **campus/** — the physical and service layer: departments, faculty, labs, library, facilities, hostels, health, transport, and general campus services.
- **student-life/** — everything outside the classroom: clubs, fests, sports, research culture, career growth, alumni, and international programs.
- **policies/** — conduct and safety: computing conduct, the general code of conduct, and the dedicated anti-ragging/grievance path. Kept separate from `administration/` because these documents encode *behavioral* rules and escalation paths, not organizational structure.
- **faq/** — a genuine student quick-answers page (duplicate ID cards, transcripts, timetable clashes, fee deadlines, grade appeals) — the kind of page a registrar's office actually publishes, not a page about the assistant.

Several documents deliberately cross-reference each other by name rather than by link (a grade dispute in `grading-and-backlogs.md` points a student to the General Grievance Redressal Committee; a ragging report in `anti-ragging-and-grievance-redressal.md` is explicitly prioritized over a routine request) — this mirrors how a real handbook is never a flat list of independent facts, and how real institutional documents reference each other in prose ("see the Student Code of Conduct") rather than with hyperlinks.

---

## 🔎 Retrieval Expectations

The corpus should support questions that require:

- direct fact retrieval;
- combining information from multiple sections or documents;
- comparing adjacent policies (a grade grievance vs. a fee grievance vs. a safety report);
- finding procedural steps;
- identifying the correct office or committee for a request;
- distinguishing static knowledge from something that requires a live tool (attendance math, event availability, an official record);
- answering follow-up questions using conversation context.

The agent should cite the document names used to construct an answer wherever possible. See [`backend/README.md`](../backend/README.md#-rag-pipeline) for how chunking, embedding, and the relevance cutoff actually work.

---

## Example Questions

### Curriculum and Degree Structure

- How many semesters does the degree take?
- What's the difference between a program elective and an open elective?
- Can I pursue a minor alongside my main degree?
- What subjects would I typically study in my third semester?
- How should I choose between two electives?

### Grading and Backlogs

- How is CGPA calculated?
- Can you calculate my SGPA if I give you my credits and grades?
- What's the difference between revaluation and re-evaluation?
- How do I clear a backlog?
- What happens if my CGPA drops too low?

### Attendance and Academic Standing

- What is the minimum attendance requirement?
- I attended 34 out of 42 classes. What is my attendance?
- How many classes can I miss before falling below 75%?

### Examinations and Evaluation

- How does continuous assessment work?
- What should I check before an examination?
- How are project courses typically evaluated?

### Academic Calendar

- What are the main stages of a semester?
- When should I verify my examination timetable?

### Academic Support

- Who should I contact about a course-specific deadline?
- Can you turn my syllabus into a study plan?

### Administration and Governance

- Who do I contact for a transcript request?
- What's the difference between the Registrar's Office and the Dean of Academics?
- Who handles hostel-related discipline issues?

### Admissions and Fee Structure

- What are the different fee components for a semester?
- What happens if I can't pay my fees on time?
- What are the different ways to get admitted here?

### Placement Cell

- How does the campus placement process work?
- What's the difference between a product company and a service company recruiter?
- Am I eligible for placements this year?

### Faculty and Departments Directory

- Who is the HOD of Computer Science and Engineering?
- Who should I contact for a course-specific issue vs. a department-wide issue?
- How do I find a faculty member for project guidance?

### Departments and Programs

- What does Information Science and Engineering focus on?
- Which department would be relevant to embedded systems?
- Can students work across departments?

### Labs and Research Centres

- Which lab works on AI research?
- Where would I go for robotics research?
- Which centre should I contact for cybersecurity research?

### Library

- Is the library open on Saturday?
- Where should I go for quiet study?

### Facilities

- Where is the seminar hall?
- Which building has computer laboratories?

### Hostel and Accommodation

- What hostel blocks are available?
- What's the guest policy for hostel residents?
- What should I do if my hostel room has a maintenance issue?

### Health and Medical Centre

- What should I do in a medical emergency on campus?
- What are the Health Centre's operating hours?
- Does the campus offer health insurance to students?

### Transportation Routes

- Which shuttle route goes to the Sports Complex?
- How often does the hostel loop shuttle run?
- Where can I park on campus?

### Dining and Transport

- When does the cafeteria serve lunch?
- Is there campus shuttle service?

### Campus Services

- Who should I contact for Wi-Fi problems?
- Can you help me report a lost ID?

### Clubs and Communities

- Which club would suit someone interested in AI?
- Are there any technical events this week?

### Fests and Cultural Events

- When does the technical fest usually happen?
- What happens during Orientation Week?

### Sports and Recreation

- What sports facilities are available on campus?
- How do intramural leagues work?

### Research and Projects

- How should I structure an engineering project?
- What makes an AI project research-worthy?

### Career Development

- What makes a project valuable on a resume?
- How should I explain my AI project in an interview?

### Alumni Network

- How does the alumni mentorship program work?
- How can I stay connected with the institution after graduating?

### International and Exchange Programs

- How do I apply for a semester exchange?
- What support exists for incoming international students?

### Scholarships and Financial Support

- What types of scholarships are available?
- Can you turn the application process into a checklist?

### Student Wellbeing

- Can you help me make a study plan?
- I have too many deadlines. How should I prioritize them?

### Digital Conduct and Computing

- Is it okay to use AI tools for an assignment?
- What should I do if someone asks for my one-time password over the phone?

### Code of Conduct and Discipline

- What counts as a serious violation vs. a minor one?
- How does the disciplinary committee process work?

### Anti-Ragging and Grievance Redressal

- What should I do if I witness ragging?
- How is a general grievance different from a ragging report?
- Who handles a sexual harassment complaint?

### Common Student Questions

- How do I get a duplicate student ID card?
- How do I request an official transcript or a bonafide certificate?
- What happens if I pay my semester fees late?
- Can I appeal a grade I think is wrong?

---

## 🧩 Notes for Contributors

- Chunking is by `##` heading (see [`backend/app/rag/ingest.py`](../backend/app/rag/ingest.py)), so every section should stand reasonably well on its own — write section headers that would make sense as a citation label, not just as prose flow.
- Write every document as if no AI system exists. No document should mention Campus Copilot, an assistant, an agent, RAG, retrieval, or "the corpus" — that's the whole point of this corpus: it should read exactly like material a real university would publish on its own, for its own students, independent of anything reading it later.
- Never link to another document with `[text](path)`. Reference other policies or offices by plain-text name instead ("the Registrar's Office," "the Student Code of Conduct") — a real handbook doesn't hyperlink to itself, and named-but-unlinked references are also a more realistic retrieval stress test than a link would be.
- When adding a fact that another document might also touch (a fee, a deadline, a committee's process), grep the rest of the corpus for it first — several documents deliberately cover adjacent ground (a grade dispute vs. a fee dispute vs. a safety report all route through different committees), and they need to agree with each other where they overlap.
- After editing anything in this directory, rebuild the index: `python -m app.rag.ingest` from `backend/` (see [`backend/README.md`](../backend/README.md#-getting-started)).
