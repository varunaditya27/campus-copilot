# Fests and Campus-Wide Events

> **Demo corpus document:** Event names, cadences, and descriptions below are fictionalized workshop data, distinct from the live event catalogue the agent queries through its tools.

## Purpose

This document describes the recurring, campus-wide event *categories* students can expect over an academic year. It is deliberately different from the structured event data the agent retrieves through `search_events` — this document explains what kind of thing a fest is and when it generally happens; the tool tells you what's actually scheduled right now.

## Annual Technical Fest

A multi-day, campus-wide technical festival typically held in the even semester (roughly February–March), combining competitive events (hackathons, coding contests, robotics challenges), workshops, guest talks from industry and academia, and project exhibitions. Technical clubs (see [`clubs-and-communities.md`](clubs-and-communities.md)) usually run individual events under the fest umbrella.

## Annual Cultural Fest

A multi-day cultural festival typically held in the odd semester (roughly September–October), featuring music, dance, drama, literary events, art, and inter-college cultural competitions. Cultural clubs and student committees coordinate logistics, sponsorship, and event scheduling.

## Sports Fest / Intramurals

An annual inter-department sports tournament spanning multiple sports (see [`sports-and-recreation.md`](sports-and-recreation.md) for facility and team details), typically held toward the end of an academic year, alongside smaller ongoing intramural leagues throughout the year.

## Orientation Week

At the start of each academic year, new students go through an orientation week covering campus familiarization, academic-system explanation, club introductions, hostel settling-in (for residents), and administrative onboarding. Orientation is also typically when students are introduced to Campus Copilot itself as a campus resource.

## Alumni Meet

An annual gathering connecting current students with alumni, often combined with mentorship sign-ups, networking sessions, and panel discussions. See [`alumni-network.md`](alumni-network.md) for how the alumni relationship works outside this single event.

## Department Day Celebrations

Individual departments often hold their own smaller annual celebration combining technical talks, alumni interaction, and department-specific competitions, distinct from the campus-wide technical fest.

## How Fests Relate to the Event System

A specific fest event (a particular hackathon slot, a particular cultural competition) is modeled as structured event data the agent can search and check availability for — the same system used for smaller club workshops. This document exists so Campus Copilot can answer "what kinds of fests happen here and roughly when" even when no specific fest is currently listed in the structured event catalogue, without inventing dates for a specific upcoming instance.
