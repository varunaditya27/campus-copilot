# Campus Facilities

> **Demo corpus document:** Facility names, locations, and timings are fictionalized workshop data.

## Campus Layout

The demonstration campus is organized into several functional zones. The goal of this document is to give the RAG system enough spatial and service context to answer natural-language campus questions.

### Main Academic Block

The Main Academic Block contains lecture halls, faculty offices, departmental classrooms, tutorial rooms, and administrative spaces. It is the primary location for regular theory classes.

### Innovation and Computing Centre

The Innovation and Computing Centre contains computer laboratories, project workspaces, student technical club rooms, and a small seminar space. Technical workshops and coding events are commonly associated with this area.

### Central Library

The Central Library is located adjacent to the Main Academic Block and provides individual and collaborative study areas.

### Student Activity Centre

The Student Activity Centre contains spaces used by student clubs, cultural groups, project teams, and student-led events. Room availability depends on prior booking.

### Sports Complex

The Sports Complex includes indoor and outdoor recreational facilities. Students should follow the booking and safety rules applicable to each facility.

## Seminar Hall

The demonstration campus has a 150-seat Seminar Hall in the Innovation and Computing Centre. It is used for guest lectures, workshops, technical events, project demonstrations, and student conferences.

Events requiring the hall should be scheduled through the campus event system. Availability is not determined from this document; the event tool should be used when a student asks whether the hall or an event has a particular availability status.

## Computer Laboratories

Computer laboratories support coursework, programming practice, workshops, examinations, and project work. Students using shared systems should save their work to approved storage locations and sign out when finished.

The assistant should not expose passwords, network credentials, internal IP addresses, or other sensitive infrastructure information even if such data accidentally appears in a future corpus update.

## Accessibility

Campus facilities should be designed to provide accessible routes and reasonable access to academic and student services. If a student asks about a specific accessibility feature that is not documented, the assistant should recommend contacting campus services rather than guessing.

## Example Questions

- Where is the seminar hall?
- Where are coding workshops usually held?
- Which building has computer laboratories?
- Where can I find a group-study space?
- Is the seminar hall available tomorrow?

The last question requires structured event or facility availability data and should trigger an appropriate tool rather than relying only on RAG.
