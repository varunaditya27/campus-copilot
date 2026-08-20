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

## Example Questions

### Academic Calender

- What are the main stages of a semester?
- What should I track during the semester?
- When should I verify my examination timetable?
- Can you help me build a study plan around my deadlines?
- Where should I check official academic dates?

### Academic Support

- Who should I contact about a course-specific deadline?
- How should I ask my professor for help?
- Can you turn my syllabus into a study plan?
- I have four hours today. How should I divide my time?
- What support options are available if I am struggling in a subject?

### Attendance and Academic Standing

- What is the minimum attendance requirement?
- I attended 34 out of 42 classes. What is my attendance?
- How many classes can I miss before falling below 75%?
- If I attend all ten remaining classes, what will my attendance become?
- Am I officially eligible for my examination?

### Examinations and Evaluation

- How does continuous assessment work?
- What should I check before an examination?
- How are project courses typically evaluated?
- Can you calculate my marks if I give you the assessment components?
- Where should I verify my examination timetable?

### Campus Services

- Who should I contact for Wi-Fi problems?
- Where can I get help with internship preparation?
- Who handles student activity bookings?
- Can you help me report a lost ID?
- Can you tell me my fee balance?

### Departments and Programs

- What does Information Science and Engineering focus on?
- Which department would be relevant to embedded systems?
- What kinds of projects combine electronics and AI?
- Can students work across departments?
- Which program is most relevant to a particular career?

### Dining and Transport

- When does the cafeteria serve lunch?
- Where is the seminar hall?
- Is there campus shuttle service?
- Can I park near the library?
- Is the cafeteria open right now?

### Facilities

- Where is the seminar hall?
- Where are coding workshops usually held?
- Which building has computer laboratories?
- Where can I find a group-study space?
- Is the seminar hall available tomorrow?

### Library

- Is the library open on Saturday?
- Where should I go for quiet study?
- Can I use the library for a group project?
- What digital resources might a university library provide?
- Where should I verify current library timings?

### Digital Conduct and Computing

- Can I share my OTP with the campus assistant?
- Is it okay to use AI for an assignment?
- Can I test a security vulnerability on a campus system?
- What should I do if my account may be compromised?
- Can I upload confidential college documents to an AI tool?

### Career Development

- What makes a project valuable on a resume?
- How should I explain my AI project in an interview?
- What should I document in an AI repository?
- How can I prepare for a software internship?
- What skills should I build for an AI engineering role?

### Clubs and Communities

- Which club would suit someone interested in AI?
- What does a coding club typically do?
- How can I get started with cybersecurity?
- How should a student organize a technical workshop?
- Are there any technical events this week?

### Research and Projects

- How should I structure an engineering project?
- What makes an AI project research-worthy?
- How can I evaluate a RAG system?
- What should I measure in an agentic AI project?
- How can I turn a campus problem into a technical project?

### Scholarships and Financial Support

- What types of scholarships are available?
- What documents might a scholarship application require?
- How should I evaluate whether a scholarship is relevant to me?
- Can you turn the application process into a checklist?
- Can you submit the scholarship application for me?

### Student Wellbeing

- Can you help me make a study plan?
- I have too many deadlines. How should I prioritize them?
- What academic support options are available?
- How can I balance club activities with coursework?
- Where can I find official student support?
