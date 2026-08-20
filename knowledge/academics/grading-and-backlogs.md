# Grading, GPA, and Backlogs

> **Demo corpus document:** The grading scale, formulas, and backlog process below are illustrative workshop data and must not be treated as an official grading regulation.

## Grading Scale

The demonstration institution uses a ten-point letter-grade scale:

| Letter Grade | Grade Point | Approximate Meaning |
| --- | --- | --- |
| O | 10 | Outstanding |
| A+ | 9 | Excellent |
| A | 8 | Very Good |
| B+ | 7 | Good |
| B | 6 | Above Average |
| C | 5 | Average |
| P | 4 | Pass |
| F | 0 | Fail / Backlog |

A course result below the passing grade point is recorded as a backlog and must be cleared through a supplementary examination or a re-registration, depending on the institution's rule for that course type.

## SGPA and CGPA

Semester Grade Point Average (SGPA) and Cumulative Grade Point Average (CGPA) are computed as credit-weighted averages:

```text
SGPA = Σ (course credits × grade point) / Σ (course credits)     — for one semester
CGPA = Σ (course credits × grade point) across all completed semesters / Σ (all credits)
```

For example, a student who takes three courses in a semester with credits 4, 3, and 3, and grade points 8, 9, and 7 respectively, has:

```text
SGPA = (4×8 + 3×9 + 3×7) / (4+3+3) = (32 + 27 + 21) / 10 = 8.0
```

Campus Copilot should use a deterministic calculation for any specific SGPA/CGPA request where the student supplies real credits and grade points, rather than estimating the arithmetic itself. If the corresponding calculator tool is not available in a given deployment, the assistant should walk through the formula rather than silently guessing a number.

## Backlogs and Supplementary Examinations

A backlog (an "F" grade, or a missed examination) is normally cleared through:

1. a supplementary examination offered in a subsequent examination cycle, for theory courses; or
2. re-registration and re-attendance of the course, for courses where continuous or laboratory components cannot be reasonably reassessed through an examination alone.

Institutions typically cap the number of active backlogs a student may carry before facing a restriction on registering for higher-semester courses. The demonstration corpus does not define this cap precisely because it varies by institution and admission year — a student asking about their specific standing should be directed to the department office or academic record system.

## Revaluation vs. Re-evaluation

These two terms are often confused:

- **Revaluation** typically refers to a formal recheck of an already-evaluated answer script, sometimes involving a second examiner, requested within a defined window after results are published.
- **Re-evaluation** or **re-examination** typically refers to reattempting an assessment, most often used for backlog clearance.

The exact process, fee, and window for each differs by institution. Campus Copilot should explain the conceptual difference but should not claim to know the specific deadline or fee unless that information exists in the corpus.

## Academic Probation and Standing

A student whose CGPA falls persistently below a defined threshold, or who accumulates backlogs beyond a defined limit, may be placed under academic probation, which can come with mandatory advising, a reduced course load, or other institutional interventions. Campus Copilot should treat any question about a student's actual probation status as something that requires the official academic record, not the static knowledge corpus.

## Grade Grievances

A student who believes a grade was recorded incorrectly should first approach the course instructor, then escalate to the department office or examination cell if unresolved, following the institution's documented grievance timeline. See [`policies/anti-ragging-and-grievance-redressal.md`](../policies/anti-ragging-and-grievance-redressal.md) for how grievance committees generally operate on the demonstration campus.
