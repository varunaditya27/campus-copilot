"use client";

import { useState } from "react";
import { ApiError, downloadMyCalendar } from "@/lib/api";

// Downloads the student's registered events as a calendar file (.ics) that
// Google Calendar, Apple Calendar and Outlook can import.
export default function AddToCalendar() {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function download() {
    setBusy(true);
    setError(null);
    try {
      const url = URL.createObjectURL(await downloadMyCalendar());
      const link = document.createElement("a");
      link.href = url;
      link.download = "campus-copilot-events.ics";
      link.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not download your calendar.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <button
        type="button"
        onClick={download}
        disabled={busy}
        className="min-h-11 bg-accent px-5 py-2.5 text-small font-medium text-accent-ink transition-transform duration-150 active:scale-[0.98] disabled:opacity-60"
      >
        Add my events to calendar
      </button>
      {error && (
        <p role="alert" className="mt-2 text-small text-danger">
          {error}
        </p>
      )}
    </div>
  );
}
