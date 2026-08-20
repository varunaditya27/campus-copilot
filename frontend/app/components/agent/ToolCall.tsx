import type { ToolActivityEntry } from "@/lib/types";
import { CheckIcon, SearchIcon, AlertIcon, SpinIcon, DotIcon } from "../icons";

const TOOL_ICON: Record<ToolActivityEntry["tool"], (p: { className?: string }) => React.JSX.Element> = {
  search_events: SearchIcon,
  check_event_availability: DotIcon,
  register_for_event: CheckIcon,
  calculate_attendance: DotIcon,
};

export default function ToolCall({
  entry,
  index,
  isLast,
}: {
  entry: ToolActivityEntry;
  index: number;
  isLast: boolean;
}) {
  const Icon = TOOL_ICON[entry.tool];

  return (
    <div className="anim-rise relative flex gap-3 pb-5" style={{ animationDelay: `${index * 70}ms` }}>
      {!isLast && (
        <span className="absolute left-[9px] top-5 bottom-0 w-px bg-line" aria-hidden />
      )}
      <span
        className={`z-10 mt-0.5 flex h-[19px] w-[19px] shrink-0 items-center justify-center border ${
          entry.status === "error"
            ? "border-rust text-rust bg-cream"
            : entry.status === "running"
              ? "border-brass text-brass bg-cream"
              : "border-forest text-forest bg-cream"
        }`}
      >
        {entry.status === "running" ? (
          <SpinIcon className="h-3 w-3" />
        ) : entry.status === "error" ? (
          <AlertIcon className="h-3 w-3" />
        ) : (
          <Icon className="h-3 w-3" />
        )}
      </span>

      <div className="min-w-0 pt-px">
        <p className="font-mono text-[11px] uppercase tracking-[0.08em] text-ink-soft">
          {entry.label}
        </p>
        {entry.resultSummary && (
          <p className="mt-0.5 text-[13px] leading-snug text-ink">
            {entry.resultSummary}
          </p>
        )}
      </div>
    </div>
  );
}
