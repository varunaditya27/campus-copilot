import Link from "next/link";
import type { CampusEvent } from "@/lib/types";
import { PinIcon } from "../icons";

function formatDate(date: string) {
  const d = new Date(`${date}T00:00:00`);
  return {
    day: d.toLocaleDateString("en-US", { day: "2-digit" }),
    month: d.toLocaleDateString("en-US", { month: "short" }),
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
      className="-mx-4 grid grid-cols-[3.5rem_1fr] gap-x-4 gap-y-2 px-4 py-4 transition-colors duration-150 hover:bg-surface focus-visible:outline-2 focus-visible:outline-ink md:grid-cols-[4rem_1fr_auto]"
    >
      <div className="row-span-2 md:row-span-1">
        <span className="block text-3xl leading-none font-medium tabular-nums text-ink">{day}</span>
        <span className="mt-1 block text-small text-muted">{month}</span>
      </div>

      <div className="min-w-0">
        <h3 className="text-body font-medium text-ink">{event.name}</h3>
        <div className="mt-1 flex items-center gap-1.5 text-small text-muted">
          <PinIcon className="h-3.5 w-3.5 shrink-0" />
          <span className="truncate">{event.venue}</span>
        </div>
      </div>

      <div className="col-start-2 flex items-center gap-3 md:col-start-3 md:row-start-1 md:flex-col md:items-end md:gap-2">
        <span className="text-small tabular-nums text-ink">{event.time}</span>
        <div className="flex items-center gap-2">
          <div className="h-1 w-16 bg-ink/10">
            <div
              className={`h-full ${nearFull ? "bg-ink" : "bg-muted"}`}
              style={{ width: `${fillRatio * 100}%` }}
            />
          </div>
          <span className={`text-small ${nearFull ? "text-ink" : "text-muted"}`}>
            {seatsLeft > 0 ? `${seatsLeft} seats left` : "Full"}
          </span>
        </div>
      </div>
    </Link>
  );
}
