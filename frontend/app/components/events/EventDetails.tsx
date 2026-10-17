import Link from "next/link";
import type { CampusEvent } from "@/lib/types";
import { CalendarIcon, PinIcon, UserIcon } from "../icons";

function formatDate(date: string) {
  return new Date(`${date}T00:00:00`).toLocaleDateString("en-US", {
    weekday: "long",
    day: "numeric",
    month: "long",
    year: "numeric",
  });
}

export default function EventDetails({ event }: { event: CampusEvent }) {
  const seatsLeft = event.capacity - event.registered;
  const fillRatio = Math.min(event.registered / event.capacity, 1);

  return (
    <article className="max-w-2xl">
      <h1 className="text-3xl font-medium tracking-[-0.03em] text-balance text-ink">{event.name}</h1>
      <p className="mt-1 text-body text-muted first-letter:uppercase">
        {event.category.replace(/-/g, " ")}
      </p>

      <dl className="mt-6 grid grid-cols-1 gap-3 bg-surface p-4 sm:grid-cols-2">
        <div className="flex items-start gap-2.5">
          <CalendarIcon className="mt-0.5 h-4 w-4 shrink-0 text-muted" />
          <div>
            <dt className="text-small text-muted">
              Date &amp; Time
            </dt>
            <dd className="mt-0.5 text-small text-ink">
              {formatDate(event.date)} · {event.time}
            </dd>
          </div>
        </div>
        <div className="flex items-start gap-2.5">
          <PinIcon className="mt-0.5 h-4 w-4 shrink-0 text-muted" />
          <div>
            <dt className="text-small text-muted">
              Venue
            </dt>
            <dd className="mt-0.5 text-small text-ink">{event.venue}</dd>
          </div>
        </div>
        <div className="flex items-start gap-2.5">
          <UserIcon className="mt-0.5 h-4 w-4 shrink-0 text-muted" />
          <div>
            <dt className="text-small text-muted">
              Organizer
            </dt>
            <dd className="mt-0.5 text-small text-ink">
              {event.organizer}
            </dd>
          </div>
        </div>
        <div>
          <dt className="text-small text-muted">
            Availability
          </dt>
          <dd className="mt-1.5 flex items-center gap-2">
            <div className="h-1 w-24 bg-ground">
              <div
                className="h-full bg-ink"
                style={{ width: `${fillRatio * 100}%` }}
              />
            </div>
            <span className="text-small tabular-nums text-muted">
              {seatsLeft > 0
                ? `${seatsLeft} of ${event.capacity} seats left`
                : "Full"}
            </span>
          </dd>
        </div>
      </dl>

      <p className="mt-6 text-body text-ink">
        {event.description}
      </p>

      <div className="mt-5 flex flex-wrap gap-1.5">
        {event.tags.map((tag) => (
          <span
            key={tag}
            className="bg-surface px-2 py-0.5 text-small text-ink"
          >
            {tag}
          </span>
        ))}
      </div>

      <div className="mt-10">
        <p className="text-small leading-relaxed text-muted">
          To register, ask Campus Copilot in the{" "}
          <Link href="/" className="text-ink underline underline-offset-2 hover:decoration-2">
            chat
          </Link>
          . For example: &ldquo;Register me for {event.name}.&rdquo;
        </p>
      </div>
    </article>
  );
}
