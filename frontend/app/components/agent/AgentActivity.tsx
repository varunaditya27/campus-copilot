import type { ToolActivityEntry } from "@/lib/types";
import ToolCall from "./ToolCall";

function Steps({ entries }: { entries: ToolActivityEntry[] }) {
  return (
    <div>
      {entries.map((entry, i) => (
        <ToolCall key={entry.id} entry={entry} index={i} isLast={i === entries.length - 1} />
      ))}
    </div>
  );
}

// A side panel on wide screens; below 1024px a collapsible strip above the input.
export default function AgentActivity({
  entries,
  compact = false,
}: {
  entries: ToolActivityEntry[];
  compact?: boolean;
}) {
  if (compact) {
    if (entries.length === 0) return null;
    return (
      <details className="group bg-surface lg:hidden">
        <summary className="flex cursor-pointer list-none items-center justify-between px-5 py-3 text-small font-medium text-ink [&::-webkit-details-marker]:hidden">
          Agent activity · {entries.length} {entries.length === 1 ? "step" : "steps"}
          <svg
            aria-hidden="true"
            viewBox="0 0 16 16"
            className="h-4 w-4 transition-transform duration-200 group-open:rotate-180"
          >
            <path d="M2 5l6 6 6-6" fill="none" stroke="currentColor" strokeWidth="2" />
          </svg>
        </summary>
        <div className="thin-scroll max-h-60 overflow-y-auto px-5 pb-4">
          <Steps entries={entries} />
        </div>
      </details>
    );
  }

  return (
    <aside className="thin-scroll hidden h-full w-72 shrink-0 flex-col overflow-y-auto bg-surface lg:flex">
      <h2 className="px-4 pt-4 text-small font-medium text-ink">Agent activity</h2>

      <div className="flex-1 px-4 py-4">
        {entries.length === 0 ? (
          <p className="text-small text-muted">
            No activity yet. When the agent searches campus data or calls a tool, each step is
            logged here in order.
          </p>
        ) : (
          <Steps entries={entries} />
        )}
      </div>

      <p className="px-4 pb-4 text-small text-muted">
        Tool calls are run by the backend. This log shows what the agent decided to do, not its
        internal reasoning.
      </p>
    </aside>
  );
}
