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
      <p className="font-mono text-[11px] uppercase tracking-[0.16em] text-brass">
        {event.category.replace(/-/g, " ")}
      </p>
      <h1 className="mt-2 font-display text-3xl font-medium leading-tight text-ink">
        {event.name}
      </h1>

      <dl className="mt-6 grid grid-cols-1 gap-3 border border-line bg-cream-raised p-4 sm:grid-cols-2">
        <div className="flex items-start gap-2.5">
          <CalendarIcon className="mt-0.5 h-4 w-4 shrink-0 text-brass" />
          <div>
            <dt className="font-mono text-[10px] uppercase tracking-[0.1em] text-ink-faint">
              Date &amp; Time
            </dt>
            <dd className="mt-0.5 text-[13.5px] text-ink">
              {formatDate(event.date)} · {event.time}
            </dd>
          </div>
        </div>
        <div className="flex items-start gap-2.5">
          <PinIcon className="mt-0.5 h-4 w-4 shrink-0 text-brass" />
          <div>
            <dt className="font-mono text-[10px] uppercase tracking-[0.1em] text-ink-faint">
              Venue
            </dt>
            <dd className="mt-0.5 text-[13.5px] text-ink">{event.venue}</dd>
          </div>
        </div>
        <div className="flex items-start gap-2.5">
          <UserIcon className="mt-0.5 h-4 w-4 shrink-0 text-brass" />
          <div>
            <dt className="font-mono text-[10px] uppercase tracking-[0.1em] text-ink-faint">
              Organizer
            </dt>
            <dd className="mt-0.5 text-[13.5px] text-ink">
              {event.organizer}
            </dd>
          </div>
        </div>
        <div>
          <dt className="font-mono text-[10px] uppercase tracking-[0.1em] text-ink-faint">
            Availability
          </dt>
          <dd className="mt-1.5 flex items-center gap-2">
            <div className="h-1 w-24 bg-cream-sunken">
              <div
                className="h-full bg-brass"
                style={{ width: `${fillRatio * 100}%` }}
              />
            </div>
            <span className="font-mono text-[11px] text-ink-soft">
              {seatsLeft > 0
                ? `${seatsLeft} of ${event.capacity} seats left`
                : "Full"}
            </span>
          </dd>
        </div>
      </dl>

      <p className="mt-6 text-[14.5px] leading-relaxed text-ink-soft">
        {event.description}
      </p>

      <div className="mt-5 flex flex-wrap gap-1.5">
        {event.tags.map((tag) => (
          <span
            key={tag}
            className="border border-line px-2 py-0.5 font-mono text-[10.5px] uppercase tracking-[0.06em] text-ink-faint"
          >
            {tag}
          </span>
        ))}
      </div>

      <div className="mt-8 border-t border-line pt-5">
        <p className="text-[13px] leading-relaxed text-ink-faint">
          To register, ask Campus Copilot in the{" "}
          <Link href="/" className="text-navy underline decoration-brass decoration-2 underline-offset-2">
            chat
          </Link>{" "}
          — for example, &ldquo;Register me for {event.name}.&rdquo;
        </p>
      </div>
    </article>
  );
}
