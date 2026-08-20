# Admissions and Fee Structure

> **Demo corpus document:** Admission routes, fee categories, and amounts below are fictionalized workshop data and must never be treated as real tuition figures.

## Admission Routes

The demonstration campus admits students through a small set of illustrative routes:

- **Merit-based entrance admission** — based on a state or national engineering entrance examination rank.
- **Management-quota admission** — a limited number of seats admitted through an institution-managed process.
- **Lateral entry** — diploma holders admitted directly into the third semester of an appropriate program.
- **Transfer admission** — in rare, institution-approved cases, a student transferring from another recognized program.

Admission criteria, cutoffs, and seat matrices change every academic year and are not stored in this static corpus. Campus Copilot should never state a specific cutoff rank or seat count as current fact.

## Fee Categories

A demonstration engineering program's annual fee is typically composed of:

| Component | Purpose |
| --- | --- |
| Tuition Fee | Core academic instruction cost |
| Development Fee | Campus infrastructure and facility upkeep |
| Examination Fee | Per-semester examination administration |
| Laboratory Fee | Department-specific lab consumables and equipment access |
| Hostel Fee | Accommodation, applicable only to resident students |
| Mess Fee | Dining plan, applicable only to students opting in |
| Caution Deposit | Refundable deposit held against damage or dues, returned at course completion |

Exact amounts are institution- and year-specific and are deliberately not included in this demonstration corpus. A production deployment would source these from a verified, regularly-updated fee schedule rather than a static markdown document, since fee figures change annually and carry real financial consequences if stated incorrectly.

## Payment Windows

Fees are typically collected once per semester, ahead of the teaching period, with a published due date and a shorter late-payment window that may carry a penalty. A student who cannot meet a payment deadline should contact Finance and Accounts (see [`administration-and-governance.md`](administration-and-governance.md)) before the deadline passes rather than after, since extensions are far easier to arrange proactively.

## Fee-Related Support

Students facing financial difficulty should be pointed toward the scholarship and financial-support pathways described in [`scholarships-and-financial-support.md`](../student-life/scholarships-and-financial-support.md), as well as Finance and Accounts directly for structured-payment or hardship discussions.

## Refunds and Withdrawal

A student withdrawing from the program may be eligible for a partial fee refund depending on the timing of withdrawal relative to the academic calendar, following the institution's refund policy. Campus Copilot should not estimate a refund amount; this always requires the current, official refund schedule.

## What Campus Copilot Should Never Do Here

- State a specific tuition, hostel, or mess fee amount as current fact.
- Confirm that a specific student's fees have been paid (this requires an authenticated student-record system, not the static corpus).
- Promise a refund, waiver, or fee extension on the institution's behalf.
