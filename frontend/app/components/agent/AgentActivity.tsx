import type { ToolActivityEntry } from "@/lib/types";
import ToolCall from "./ToolCall";

export default function AgentActivity({
  entries,
}: {
  entries: ToolActivityEntry[];
}) {
  return (
    <aside className="thin-scroll flex h-full w-72 shrink-0 flex-col overflow-y-auto border-l border-line bg-cream-sunken/60">
      <div className="rule-bottom border-line px-4 py-3">
        <h2 className="font-mono text-[11px] uppercase tracking-[0.16em] text-ink-soft">
          Agent Activity
        </h2>
      </div>

      <div className="flex-1 px-4 py-4">
        {entries.length === 0 ? (
          <p className="font-mono text-[11px] leading-relaxed text-ink-faint">
            No activity yet. When the agent searches campus data or calls a
            tool, each step will be logged here in order.
          </p>
        ) : (
          <div>
            {entries.map((entry, i) => (
              <ToolCall
                key={entry.id}
                entry={entry}
                index={i}
                isLast={i === entries.length - 1}
              />
            ))}
          </div>
        )}
      </div>

      <div className="rule-top border-line px-4 py-3">
        <p className="font-mono text-[10.5px] leading-relaxed text-ink-faint">
          Tool calls are executed by the backend. This log shows what the
          agent decided to do — not its internal reasoning.
        </p>
      </div>
    </aside>
  );
}
