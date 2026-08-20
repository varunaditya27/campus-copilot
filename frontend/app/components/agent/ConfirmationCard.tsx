"use client";

import { useState } from "react";
import type { RegistrationConfirmation } from "@/lib/types";
import { confirmRegistration, ApiError } from "@/lib/api";
import { CalendarIcon, PinIcon, UserIcon, CheckIcon } from "../icons";

type Status = "idle" | "submitting" | "success" | "error" | "cancelled";

export default function ConfirmationCard({
  confirmation,
}: {
  confirmation: RegistrationConfirmation;
}) {
  const [status, setStatus] = useState<Status>("idle");
  const [registrationId, setRegistrationId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const { event, studentId } = confirmation;

  async function handleConfirm() {
    setStatus("submitting");
    setError(null);
    try {
      const res = await confirmRegistration({
        event_id: event.id,
        student_id: studentId,
      });
      if (res.success) {
        setRegistrationId(res.registration_id ?? null);
        setStatus("success");
      } else {
        setError(res.error ?? "Registration could not be completed.");
        setStatus("error");
      }
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : "Registration could not be completed.",
      );
      setStatus("error");
    }
  }

  if (status === "success") {
    return (
      <div className="anim-rise max-w-md border border-forest bg-cream-raised">
        <div className="flex items-center gap-2 bg-forest px-4 py-2 text-cream">
          <CheckIcon className="h-4 w-4" />
          <span className="font-mono text-[11px] uppercase tracking-[0.14em]">
            Registration Confirmed
          </span>
        </div>
        <div className="px-4 py-3">
          <p className="text-[14px] text-ink">{event.name}</p>
          {registrationId && (
            <p className="mt-1 font-mono text-[12px] text-ink-soft">
              Registration ID: {registrationId}
            </p>
          )}
        </div>
      </div>
    );
  }

  if (status === "cancelled") {
    return (
      <div className="anim-rise max-w-md border border-line bg-cream-raised px-4 py-3">
        <p className="font-mono text-[11px] uppercase tracking-[0.14em] text-ink-faint">
          Registration cancelled
        </p>
      </div>
    );
  }

  return (
    <div className="anim-rise max-w-md border border-brass-line bg-cream-raised">
      <div className="flex items-center justify-between bg-navy px-4 py-2 text-cream">
        <span className="font-mono text-[11px] uppercase tracking-[0.14em]">
          Registration Confirmation
        </span>
        <span className="font-mono text-[10px] uppercase tracking-[0.1em] text-brass-soft">
          Requires approval
        </span>
      </div>

      <dl className="rule-bottom border-line px-4 py-3">
        <div className="font-display text-[16px] font-medium text-ink">
          {event.name}
        </div>
        <div className="mt-2.5 space-y-1.5 text-[13px] text-ink-soft">
          <div className="flex items-center gap-2">
            <CalendarIcon className="h-3.5 w-3.5 text-brass" />
            <span>
              {event.date} · {event.time}
            </span>
          </div>
          <div className="flex items-center gap-2">
            <PinIcon className="h-3.5 w-3.5 text-brass" />
            <span>{event.venue}</span>
          </div>
          <div className="flex items-center gap-2">
            <UserIcon className="h-3.5 w-3.5 text-brass" />
            <span className="font-mono">{studentId}</span>
          </div>
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
          onClick={handleConfirm}
          disabled={status === "submitting"}
          className="flex-1 border-r border-line bg-brass px-4 py-2.5 font-mono text-[12px] uppercase tracking-[0.1em] text-cream transition-colors duration-150 hover:bg-navy disabled:opacity-60"
        >
          {status === "submitting" ? "Registering…" : "Confirm"}
        </button>
        <button
          type="button"
          onClick={() => setStatus("cancelled")}
          disabled={status === "submitting"}
          className="flex-1 px-4 py-2.5 font-mono text-[12px] uppercase tracking-[0.1em] text-ink-soft transition-colors duration-150 hover:bg-cream-sunken disabled:opacity-60"
        >
          Cancel
        </button>
      </div>
    </div>
  );
}
