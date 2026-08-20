import Link from "next/link";
import type { CampusEvent } from "@/lib/types";
import { PinIcon } from "../icons";

function formatDate(date: string) {
  const d = new Date(`${date}T00:00:00`);
  return {
    day: d.toLocaleDateString("en-US", { day: "2-digit" }),
    month: d.toLocaleDateString("en-US", { month: "short" }).toUpperCase(),
  };
}

export default function EventCard({ event }: { event: CampusEvent }) {
  const { day, month } = formatDate(event.date);
  const seatsLeft = event.capacity - event.registered;
  const fillRatio = Math.min(event.registered / event.capacity, 1);
  const nearFull = seatsLeft <= 5;

  return (
    <Link
      href={`/events/${event.id}`}
      className="group flex gap-4 border border-line bg-cream-raised p-4 transition-colors duration-150 hover:border-brass-line hover:bg-cream"
    >
      <div className="flex w-14 shrink-0 flex-col items-center justify-center border-r border-line pr-4 text-center">
        <span className="font-display text-2xl font-medium leading-none text-navy">
          {day}
        </span>
        <span className="mt-1 font-mono text-[10px] uppercase tracking-[0.12em] text-ink-faint">
          {month}
        </span>
      </div>

      <div className="min-w-0 flex-1">
        <div className="flex items-start justify-between gap-3">
          <h3 className="font-display text-[16px] font-medium leading-snug text-ink group-hover:text-navy">
            {event.name}
          </h3>
          <span className="shrink-0 font-mono text-[11px] text-ink-faint">
            {event.time}
          </span>
        </div>

        <div className="mt-1 flex items-center gap-1.5 text-[12.5px] text-ink-soft">
          <PinIcon className="h-3 w-3 shrink-0 text-brass" />
          <span className="truncate">{event.venue}</span>
        </div>

        <div className="mt-3 flex items-center gap-3">
          <div className="h-1 flex-1 max-w-32 bg-cream-sunken">
            <div
              className={`h-full ${nearFull ? "bg-rust" : "bg-brass"}`}
              style={{ width: `${fillRatio * 100}%` }}
            />
          </div>
          <span
            className={`font-mono text-[10.5px] uppercase tracking-[0.08em] ${
              nearFull ? "text-rust" : "text-ink-faint"
            }`}
          >
            {seatsLeft > 0 ? `${seatsLeft} seats left` : "Full"}
          </span>
        </div>
      </div>
    </Link>
  );
}
