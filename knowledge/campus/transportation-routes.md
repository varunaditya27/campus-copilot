# Campus Shuttle Routes

> **Demo corpus document:** Route names, stops, and timings below are fictionalized workshop data, distinct from the general transport policy in [`dining-and-transport.md`](dining-and-transport.md).

## Purpose

This document gives the RAG system concrete, structured-feeling route data to demonstrate that even "structured" looking information can live in the static knowledge corpus when it changes slowly — while genuinely live data (is the shuttle running right now, is it delayed) still belongs in a real-time or structured system, not here.

## Shuttle Routes

### Route A — City Gate Line

Connects the main city-side entrance to the academic core.

```text
Main Gate → Central Library → Main Academic Block → Innovation and Computing Centre → Hostel Blocks
```

Runs approximately every 20 minutes during peak hours (7:30 AM – 9:30 AM and 4:30 PM – 6:30 PM), and every 40 minutes during off-peak daytime hours.

### Route B — Hostel Loop

A short internal loop primarily serving hostel residents.

```text
Ashoka Block → Nilgiri Block → Kaveri Block → Vindhya Block → Student Activity Centre → Main Academic Block
```

Runs approximately every 15 minutes between 7:00 AM and 10:00 PM.

### Route C — Sports and Recreation Line

Connects academic areas to the Sports Complex, primarily useful around practice and tournament timings.

```text
Main Academic Block → Innovation and Computing Centre → Sports Complex
```

Runs approximately every 30 minutes between 4:00 PM and 8:00 PM on weekdays, with an extended schedule on weekend tournament days.

## Boarding Notes

- Shuttles operate on a first-come, first-served basis; there is no seat reservation system.
- Priority boarding is given to students with mobility-related accessibility needs.
- Shuttle service is suspended during declared campus holidays and severe weather advisories.

## Parking

Designated parking areas exist near the Main Gate, the Sports Complex, and select academic buildings for students and staff with registered vehicles. Unregistered vehicles or those parked in restricted zones (fire lanes, accessibility spaces, reserved faculty areas) may be subject to campus access enforcement. See [`dining-and-transport.md`](dining-and-transport.md) for general parking conduct expectations.

## What This Document Does Not Answer

This document describes the *designed* route network, not live shuttle location or delay status. A question like "is Route A running late right now?" requires a live tracking system, not this markdown file — Campus Copilot should say so rather than guessing based on the published schedule.
