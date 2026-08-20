"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import type { CampusEvent } from "@/lib/types";
import { getEvent, ApiError } from "@/lib/api";
import EventDetails from "../../components/events/EventDetails";
import { ArrowRightIcon } from "../../components/icons";

export default function EventDetailPage() {
  const params = useParams<{ id: string }>();
  const [event, setEvent] = useState<CampusEvent | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getEvent(params.id)
      .then(setEvent)
      .catch((err) =>
        setError(
          err instanceof ApiError ? err.message : "Could not load this event.",
        ),
      );
  }, [params.id]);

  return (
    <div className="thin-scroll flex-1 overflow-y-auto px-6 py-10">
      <div className="mx-auto max-w-2xl">
        <Link
          href="/events"
          className="inline-flex items-center gap-1.5 font-mono text-[11px] uppercase tracking-[0.12em] text-ink-faint transition-colors hover:text-navy"
        >
          <ArrowRightIcon className="h-3 w-3 rotate-180" />
          All events
        </Link>

        <div className="mt-6">
          {error && (
            <div className="border border-line bg-rust/5 px-4 py-3">
              <p className="font-mono text-[12px] text-rust">{error}</p>
            </div>
          )}
          {!error && !event && (
            <p className="font-mono text-[12px] text-ink-faint">Loading…</p>
          )}
          {event && <EventDetails event={event} />}
        </div>
      </div>
    </div>
  );
}
