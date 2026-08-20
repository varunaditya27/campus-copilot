# Faculty and Department Directory

> **Demo corpus document:** Names, titles, and office-hour conventions below are entirely fictionalized workshop data and do not represent real people.

## Purpose

This document gives the RAG system a realistic sense of faculty structure and how students should approach reaching a faculty member — without shipping a real personal directory, which would be inappropriate to fabricate in a demo corpus. Names below are illustrative placeholders only.

## Department Structure

Every department follows the same general staffing pattern:

```text
Head of Department (HOD)
      │
      ├── Professors
      ├── Associate Professors
      ├── Assistant Professors
      └── Teaching Assistants / Lab Instructors
```

Course coordinators (usually an Assistant or Associate Professor) are assigned per course per semester and are the correct first point of contact for that specific course.

## Illustrative Department Contacts

| Department | Head of Department (illustrative) | General Office Email Pattern |
| --- | --- | --- |
| Information Science and Engineering | Dr. R. Venkatesh | hod.ise@example-university.edu |
| Computer Science and Engineering | Dr. S. Krishnan | hod.cse@example-university.edu |
| Electronics and Communication Engineering | Dr. A. Fernandes | hod.ece@example-university.edu |
| Electrical and Electronics Engineering | Dr. P. Deshmukh | hod.eee@example-university.edu |
| Mechanical Engineering | Dr. N. Subramanian | hod.me@example-university.edu |

The email domain `example-university.edu` is a placeholder and does not resolve to a real system. A production deployment would source this directory from institutional HR/faculty data, kept current, rather than a static file that will drift out of date as faculty join or leave.

## Reaching a Faculty Member

The correct channel depends on what the student needs:

1. **Course-specific question** → the course instructor or coordinator, usually reachable via institutional email or during posted office hours.
2. **Department-level academic issue** (registration, elective approval, project guide allocation) → the department office or HOD.
3. **Research supervision or project guidance** → a faculty member whose research area matches the student's interest; see [`labs-and-research-centres.md`](labs-and-research-centres.md) for area-to-lab mapping.
4. **General administrative matters** → the offices described in [`administration-and-governance.md`](../administration/administration-and-governance.md), not an individual faculty member.

## Office Hours Convention

Faculty at the demonstration campus typically publish weekly office hours during which students can drop in without a prior appointment. Outside those hours, students should email to request a meeting rather than assume availability. Campus Copilot should never invent a specific faculty member's office hours, office location, or personal contact detail — this document intentionally omits that level of specificity because it is not reliable demo data.

## Visiting and Adjunct Faculty

Some courses, particularly emerging-technology electives, may be taught by visiting industry practitioners or adjunct faculty. These instructors may have different availability patterns than full-time faculty, and students should confirm communication channels at the start of the course.
