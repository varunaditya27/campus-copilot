"use client";

import { useState } from "react";
import type { ActionOutcome, Confirmation } from "@/lib/types";
import { ApiError, cancelAction, confirmAction } from "@/lib/api";
import { CheckIcon } from "../icons";

type Status = "idle" | "submitting" | "done" | "failed" | "cancelled" | "expired";

// Shows what the assistant proposes to do, and does it only when the student says so.
export default function ConfirmationCard({
  confirmation,
}: {
  confirmation: Confirmation;
}) {
  const [status, setStatus] = useState<Status>("idle");
  const [outcome, setOutcome] = useState<ActionOutcome | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function run(decision: "confirm" | "cancel") {
    setStatus("submitting");
    setError(null);
    try {
      const result =
        decision === "confirm"
          ? await confirmAction(confirmation.action_id)
          : await cancelAction(confirmation.action_id);
      setOutcome(result);
      setStatus(
        result.status === "cancelled" ? "cancelled" : result.success ? "done" : "failed",
      );
    } catch (err) {
      if (err instanceof ApiError && err.status === 410) {
        setStatus("expired");
        return;
      }
      setError(err instanceof ApiError ? err.message : "Something went wrong. Please try again.");
      setStatus("idle");
    }
  }

  if (status === "done" && outcome) {
    return (
      <div className="anim-rise max-w-md border border-forest bg-cream-raised">
        <div className="flex items-center gap-2 bg-forest px-4 py-2 text-cream">
          <CheckIcon className="h-4 w-4" />
          <span className="font-mono text-[11px] uppercase tracking-[0.14em]">Done</span>
        </div>
        <div className="px-4 py-3">
          <p className="text-[14px] text-ink">{outcome.message}</p>
          {Object.entries(outcome.details).map(([label, value]) => (
            <p key={label} className="mt-1 font-mono text-[12px] text-ink-soft">
              {label}: {value}
            </p>
          ))}
        </div>
      </div>
    );
  }

  if (status === "failed" && outcome) {
    return (
      <div className="anim-rise max-w-md border border-rust/40 bg-rust/5 px-4 py-3">
        <p className="font-mono text-[11px] uppercase tracking-[0.14em] text-rust">
          Not done
        </p>
        <p className="mt-1 text-[13.5px] text-ink">{outcome.message}</p>
      </div>
    );
  }

  if (status === "cancelled" || status === "expired") {
    return (
      <div className="anim-rise max-w-md border border-line bg-cream-raised px-4 py-3">
        <p className="font-mono text-[11px] uppercase tracking-[0.14em] text-ink-faint">
          {status === "cancelled"
            ? "Cancelled. Nothing was done."
            : "This took too long to approve. Ask again if you still want it."}
        </p>
      </div>
    );
  }

  return (
    <div className="anim-rise max-w-md border border-brass-line bg-cream-raised">
      <div className="flex items-center justify-between bg-navy px-4 py-2 text-cream">
        <span className="font-mono text-[11px] uppercase tracking-[0.14em]">
          Please confirm
        </span>
        <span className="font-mono text-[10px] uppercase tracking-[0.1em] text-brass-soft">
          Requires approval
        </span>
      </div>

      <dl className="rule-bottom border-line px-4 py-3">
        <div className="font-display text-[16px] font-medium text-ink">
          {confirmation.title}
        </div>
        <div className="mt-2.5 space-y-1.5 text-[13px] text-ink-soft">
          {confirmation.lines.map((line) => (
            <div key={line.label} className="flex gap-3">
              <dt className="w-16 shrink-0 font-mono text-[11px] uppercase tracking-[0.1em] text-ink-faint">
                {line.label}
              </dt>
              <dd>{line.value}</dd>
            </div>
          ))}
        </div>
      </dl>

      {error && (
        <p className="rule-bottom border-line bg-rust/5 px-4 py-2 text-[12.5px] text-rust">
          {error}
        </p>
      )}

      <div className="flex">
        <button
          type="button"
          onClick={() => run("confirm")}
          disabled={status === "submitting"}
          className="flex-1 border-r border-line bg-brass px-4 py-2.5 font-mono text-[12px] uppercase tracking-[0.1em] text-cream transition-colors duration-150 hover:bg-navy disabled:opacity-60"
        >
          {status === "submitting" ? "Working…" : "Confirm"}
        </button>
        <button
          type="button"
          onClick={() => run("cancel")}
          disabled={status === "submitting"}
          className="flex-1 px-4 py-2.5 font-mono text-[12px] uppercase tracking-[0.1em] text-ink-soft transition-colors duration-150 hover:bg-cream-sunken disabled:opacity-60"
        >
          Cancel
        </button>
      </div>
    </div>
  );
}
