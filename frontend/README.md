<div align="center">

# Frontend

The chat, events, profile and admin screens of Campus Copilot, as an installable web app.

</div>

This package is the presentation layer. It owns the screens and what the browser keeps. It does not own retrieval, tools or the agent, which live in the [backend](../backend/README.md). It is a typed client of the backend's API. The endpoints are listed in the backend's API section, and the [architecture](../docs/architecture.md) shows how the parts fit together.

## The screens

- Chat (`/`): the conversation with the agent. Replies stream in as they are written, a side panel shows each tool the agent runs in plain words, retrieved documents appear as source cards, and an action the agent proposes appears as a confirmation card. After a confirmed registration the card offers a calendar file.
- Events (`/events`, `/events/[id]`): a read-only browser of campus events, independent of the chat.
- Profile (`/profile`): a student's details and interests, a download of their registered events as a calendar file, the switch for push notifications, and an install prompt.
- Sign in and sign up (`/login`, `/register`).
- Dashboard (`/admin`): for faculty, staff and administrators. See below.
- Offline page (`/~offline`): shown when a page that was never opened is requested without a connection.

## Design system

The interface is olive on bone: one ground, one ink, one accent, and one typeface, Hanken Grotesk. Surfaces are flat, and the only shadow is on the modal dialog. The mark and the wider brand rules are in the [brand notes](../assets/brand/brand.md).

The tokens live in [`app/globals.css`](app/globals.css) as CSS custom properties, mapped into Tailwind v4 with `@theme inline`:

- ground `#ecebe7` (bone), the page;
- surface `#e1dfd9`, cards and panels;
- ink `#38450f` (olive), text and buttons; it is also the accent;
- muted `#5d683a`, secondary text;
- danger `#8b1e24`, for errors and failures only;
- five chart colours, used in a fixed order and never cycled.

Ink on ground has a contrast ratio of 8.69 to 1, and muted on ground 5.02 to 1. Chat messages are a labelled transcript and not rounded bubbles. Replies are Markdown, because answers routinely include lists and tables, and [`app/components/chat/Markdown.tsx`](app/components/chat/Markdown.tsx) styles each element itself. Icons are hand-built in [`app/components/icons.tsx`](app/components/icons.tsx); there is no icon library.

## How it talks to the backend

Every call goes through [`lib/api.ts`](lib/api.ts). The backend owns sign-in: tokens live in HttpOnly cookies that page scripts cannot read, so requests are sent with `credentials: "include"` and the page asks the backend who is signed in. When a call answers 401, the short-lived access token has expired; the client renews it once and retries, and if that fails the session is treated as ended.

The chat uses `POST /api/chat/stream`, which answers with server-sent events. Each event is a `data:` line holding `{ "type": ..., "payload": ... }`:

- `rag_context`: the sources found.
- `token`: a piece of text to append to the reply.
- `reset`: clear the reply streamed so far, because the model is about to call a tool.
- `tool_start` and `tool_done`: a tool began or finished.
- `done`: the full reply, with its sources, tool activity and any confirmation.
- `error`: something failed after streaming began.

When the agent proposes an action, `done` carries a confirmation. The card shows it, and Confirm or Cancel sends back only the proposal's id (`POST /api/actions/:id/confirm` or `/cancel`). The details never come from the browser.

## Installable app and offline use

The app has a manifest ([`app/manifest.ts`](app/manifest.ts)) and a service worker ([`app/sw.ts`](app/sw.ts)), built by Serwist at `/serwist/sw.js`. The worker exists only in production builds, so it cannot be tried with `npm run dev`.

- The app shell is precached, so pages open without a connection.
- Three API answers are kept so they can be read offline: the events, who is signed in, and the last conversation. They share one cache, `campus-copilot-api`.
- No other API answer is ever kept. The profile, registrations and the calendar file are always fetched live.
- That cache is cleared when a session ends, when it expires, and when someone signs in, so nothing kept for one person is readable by the next. Signing out also removes the browser's push subscription from the server.
- The worker shows push notifications and opens the page they name when one is tapped, but only pages on this site.
- Where the browser offers installation the profile page shows an install button; on iPhone and iPad it explains Add to Home Screen.

## The dashboard

`/admin` is for signed-in faculty, staff and administrators. Students are told it is not for them, and the Dashboard link shows only for the other roles. The tabs follow the backend's permissions: faculty see Events and can manage only their own department's events, staff see Grievances, and administrators see everything.

- Events: deleting an event that has registrations first shows how many students are affected and only deletes after a second confirmation. The roster page has a capacity gauge and downloads the registrations as CSV.
- Students: search waits for a pause in typing. The import is all or nothing and shows every problem.
- Knowledge: a re-ingest is one request that can take up to a minute, so the progress indicator is a pulse with the elapsed seconds, not a percentage. The chunk preview shows the embedding model and vector size.
- Grievances: drag a ticket between columns, or use the menu on the card, which is the keyboard route. A ticket moves on screen at once and snaps back if the server refuses. Resolving needs a note.
- Analytics: the charts are plain SVG, with no charting library. Words appear in the word cloud only after two questions have used them.

## Layout

- `app/` holds the routes listed above, `sw.ts`, `manifest.ts` and the `serwist/` route that builds the worker.
- `app/components/` is split by area: `layout`, `chat`, `agent`, `rag`, `events`, `auth` and `notifications`, plus the shared `icons.tsx`.
- `app/admin/` is the dashboard, with its shared pieces in `_components/`.
- `lib/` holds the API client (`api.ts`, `adminApi.ts`), the types (`types.ts`, `adminTypes.ts`), which role sees which dashboard section, the offline cache and push helpers, and the small functions that turn agent events into screen state.

## Running it

[Getting started](../docs/getting-started.md) covers setup. The scripts are:

- `npm run dev`: the development server.
- `npm run build` and `npm run start`: a production build and serving it.
- `npm run lint`: ESLint.
- `npm test`: the component tests (Vitest).

Type checking needs Next's generated route types, which a fresh checkout does not have, so run `npx next typegen` once before `npx tsc --noEmit`.

## Notes for contributors

- Keep new interface in the established look: flat surfaces, one typeface, no gradients, and no emoji used as icons. Use [`app/components/icons.tsx`](app/components/icons.tsx) for new icons.
- Design tokens live in [`app/globals.css`](app/globals.css). Extend them there and do not hard-code values in components.
- New backend endpoints go in [`lib/api.ts`](lib/api.ts) and [`lib/types.ts`](lib/types.ts), so the app stays fully typed.
- If a Markdown element renders unstyled, add an override to the `components` map in [`app/components/chat/Markdown.tsx`](app/components/chat/Markdown.tsx). Do not use the Typography plugin or inline styles.
- This version of Next.js has breaking changes from older ones. Read the matching guide in `node_modules/next/dist/docs/` before changing how routes, metadata or caching work.
