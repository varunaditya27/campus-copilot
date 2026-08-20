# Common Student Questions

> **Demo corpus:** Frequently asked questions for workshop demonstrations. Institution-specific answers must be verified before production use.

## How do I find an upcoming event?

Use the campus events system or ask Campus Copilot to search the structured event catalogue. Event discovery is different from general knowledge retrieval because event availability and schedules can change.

## Can Campus Copilot register me for an event?

In the workshop application, yes. The agent can search for an event, check availability, collect a student identifier if required, prepare a registration, and request explicit confirmation before executing the registration tool.

## Why does the assistant ask me to confirm?

Confirmation is a human-in-the-loop safety mechanism. Searching for information is generally reversible; creating a registration changes application state. The user should therefore approve the final action.

## Can the assistant tell me my official attendance?

Not from the static knowledge corpus. The corpus contains attendance policy information, not private student records. A production system would require an authenticated student-record tool with appropriate authorization.

## Can the assistant calculate attendance?

Yes. A deterministic calculator tool can compute attendance from the numbers supplied by the student. The assistant should distinguish a calculated estimate from an official attendance record.

## Where is the library?

The demonstration corpus places the Central Library adjacent to the Main Academic Block. Exact campus directions should be sourced from verified campus data in a production deployment.

## What can I ask about clubs?

Students can ask about the types of clubs, their focus areas, typical activities, and how to get started. Current membership status and event schedules should come from structured data.

## Can I ask the assistant to plan my studies?

Yes. The assistant can organize a study plan from the student's subjects, deadlines, and available time. It should avoid claiming that a particular plan guarantees success.

## Can I give the assistant my password?

No. Students should never provide passwords, OTPs, recovery codes, or other authentication secrets to an ordinary chatbot.

## Why did the assistant use a tool instead of searching the knowledge base?

Different information belongs in different systems. Static policy information is suitable for RAG. Current event availability belongs in structured application data. A calculation is best performed by deterministic code. The agent chooses the appropriate mechanism based on the task.

## Why did the assistant say it could not answer something?

A trustworthy assistant should recognize when the required information is absent or when a request requires access to protected records. Refusing to invent an answer is a feature, not a failure.

## Can the assistant submit a scholarship application?

Not in the workshop. Submitting an external application would require a dedicated authenticated tool, careful handling of personal information, and explicit user confirmation.

## What is RAG?

Retrieval-augmented generation combines semantic retrieval with language generation. The system retrieves relevant material from a knowledge base and provides that material to the LLM as context for its answer.

## What is an AI agent?

In this workshop, an agent is an LLM-powered system that can interpret a user's goal, decide which available tools are useful, observe tool results, and continue the workflow until it can provide a useful response or complete an approved action.
