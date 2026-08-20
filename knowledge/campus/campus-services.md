# Campus Services

> **Demo corpus document:** Service names, locations, and procedures are fictionalized workshop data.

## Student Services Desk

The Student Services Desk is a general first point of contact for routine campus-service questions. It can help students identify the appropriate office for documentation, facilities, student activities, and administrative processes.

The assistant should distinguish between answering a general question and performing an official administrative action. If a process requires institutional authentication or approval, Campus Copilot should explain the next step rather than pretending to have completed it.

## IT Help Desk

The IT Help Desk handles common computing and campus technology issues such as account access, approved software, laboratory systems, Wi-Fi troubleshooting, and basic device connectivity.

Students reporting a technical problem should ideally provide:

- their location or affected facility;
- the device or service involved;
- the approximate time the issue started;
- the exact error message, if any;
- steps already attempted.

The assistant should never request or expose passwords, authentication codes, recovery secrets, or private credentials.

## Career and Placement Support

Career services may assist with internship preparation, resume reviews, interview preparation, career sessions, employer events, and placement-related communication. Students should verify employer-specific eligibility and deadlines through official notices.

Campus Copilot can help a student organize preparation tasks but should not guarantee placement outcomes.

## Student Activity Support

Students planning a club event may need to coordinate venue availability, event registration, equipment requirements, and responsible organizers. The event tools in the demonstration application are intentionally simplified representations of this process.

## Administrative Requests

Administrative requests often involve records that cannot safely be inferred from a knowledge base. Examples include:

- individual academic status;
- fee balances;
- official attendance records;
- disciplinary records;
- examination results;
- personal documents.

For these cases, the assistant should explain the correct office or process rather than fabricate a result.

## Service Discovery

A useful Campus Copilot interaction is:

> "I lost my student ID. What should I do?"

The assistant should retrieve the documented process for reporting the loss and identify the responsible service. If the exact process is absent, it should say so.

## Example Questions

- Who should I contact for Wi-Fi problems?
- Where can I get help with internship preparation?
- Who handles student activity bookings?
- Can you help me report a lost ID?
- Can you tell me my fee balance?

The final question should not be answered from static corpus data unless a secure, authenticated student-record tool is explicitly implemented.
