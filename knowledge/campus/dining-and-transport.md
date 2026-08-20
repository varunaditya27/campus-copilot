# Dining, Transport, and Everyday Campus Logistics

> **Demo corpus:** Locations, timings, and services are fictionalized workshop data.

## Dining

The demonstration campus includes a central cafeteria and several smaller refreshment points. Dining facilities are intended to provide convenient meals and refreshments during academic hours.

### Central Cafeteria

For the demonstration dataset:

- Breakfast service: 8:00 AM – 10:30 AM
- Lunch service: 12:00 PM – 3:00 PM
- Evening refreshments: 4:00 PM – 6:00 PM

These timings are static corpus information. If the application later models live operating status, a structured tool should be preferred.

Students should follow posted hygiene, queue, payment, and waste-disposal guidelines. The assistant should not make claims about food safety, allergens, or nutritional suitability unless verified information is available.

## Campus Transport

A demonstration shuttle connects the main gate with academic buildings and student facilities during peak hours. Shuttle schedules can vary according to academic calendars, events, maintenance, and holidays.

A static knowledge document can explain the general purpose of the shuttle, but a question such as "Is the shuttle running right now?" should require a live or structured availability source.

## Parking

Students and visitors should use designated parking areas and follow campus access rules. Restricted or reserved areas should not be assumed to be available.

## Navigation Principles

When answering location questions, the assistant should provide:

1. building name;
2. relevant campus landmark;
3. destination area;
4. any known access restriction.

For example:

> "The Seminar Hall is in the Innovation and Computing Centre. It is commonly used for technical workshops and student conferences."

The assistant should not fabricate walking distances or turn-by-turn directions without a mapping source.

## Example Questions

- When does the cafeteria serve lunch?
- Where is the seminar hall?
- Is there campus shuttle service?
- Can I park near the library?
- Is the cafeteria open right now?

The final question is time-sensitive and should use structured/live data in a production system.
