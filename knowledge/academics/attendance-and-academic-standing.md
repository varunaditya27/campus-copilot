# Attendance and Academic Standing

> **Demo corpus document:** The rules below are fictionalized workshop data and must not be treated as an institution's official attendance policy.

## Overview

Regular attendance is an important part of the academic experience. Students are expected to attend lectures, laboratories, tutorials, seminars, project reviews, and other scheduled academic activities. Attendance is tracked separately for courses or academic components where required.

For this demonstration corpus, the minimum attendance threshold is **75%** for a student to remain ordinarily eligible for end-semester evaluation. A course may have additional requirements for laboratory participation, continuous assessment, or mandatory activities.

Attendance is normally calculated as:

```text
attendance percentage = (classes attended / classes conducted) × 100
```

The Campus Copilot should use the attendance calculator tool for numerical calculations instead of asking the language model to perform arithmetic itself.

## Understanding Attendance Status

A student can ask the assistant to calculate a current percentage, determine how many additional classes are needed to cross a target threshold, or explore hypothetical scenarios. The assistant should distinguish between:

- **current attendance:** based on classes already conducted;
- **projected attendance:** based on a hypothetical future number of classes attended;
- **official eligibility:** an institutional decision that must ultimately be verified against the current academic record.

For example, if a student has attended 34 of 42 classes, the current percentage is approximately 80.95%. If the student asks whether they are officially eligible for an examination, the assistant should explain that the calculation is above the demonstration threshold but that official eligibility depends on the institution's recorded attendance and applicable rules.

## Shortage of Attendance

Students who fall below the threshold should contact the relevant course instructor or academic office as early as possible. Waiting until the end of the semester can make recovery difficult because the number of remaining classes may be limited.

The assistant should not invent medical, disciplinary, or attendance-condonation decisions. If a student asks whether an exception will definitely be granted, the response should direct them to the appropriate academic authority.

## Improving Attendance

A useful planning interaction is:

1. Ask for classes attended.
2. Ask for classes conducted.
3. Calculate current attendance.
4. Ask how many classes remain, if known.
5. Calculate projected attendance under the student's proposed attendance plan.
6. Explain the result clearly.

The agent should prefer deterministic tools for steps 3 and 5.
