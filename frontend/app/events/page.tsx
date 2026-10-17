"use client";

import { useEffect, useState } from "react";
import type { CampusEvent } from "@/lib/types";
import { listEvents, ApiError } from "@/lib/api";
import EventCard from "../components/events/EventCard";

export default function EventsPage() {
  const [events, setEvents] = useState<CampusEvent[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listEvents()
      .then(setEvents)
      .catch((err) =>
        setError(
          err instanceof ApiError
            ? err.message
            : "Could not load campus events.",
        ),
      );
  }, []);

  return (
    <div className="thin-scroll flex-1 overflow-y-auto px-6 py-10">
      <div className="mx-auto max-w-3xl">
        <h1 className="text-3xl font-medium tracking-[-0.03em] text-ink">
          Upcoming on campus
        </h1>
        <p className="mt-2 max-w-lg text-body text-ink">
          Browse what&rsquo;s happening, or ask Campus Copilot to find and
          register you for one directly.
        </p>

        <div className="mt-8 flex flex-col gap-1">
          {error && (
            <div className="bg-danger/10 px-4 py-3">
              <p className="text-small text-danger">{error}</p>
            </div>
          )}

          {!error && events === null && (
            <p className="text-small tabular-nums text-muted">
              Loading events…
            </p>
          )}

          {events?.length === 0 && (
            <p className="text-small tabular-nums text-muted">
              No events scheduled right now.
            </p>
          )}

          {events?.map((event) => (
            <EventCard key={event.id} event={event} />
          ))}
        </div>
      </div>
    </div>
  );
}
