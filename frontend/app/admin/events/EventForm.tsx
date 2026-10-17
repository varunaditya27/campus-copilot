"use client";

import { useState } from "react";
import { createEvent, updateEvent } from "@/lib/adminApi";
import type { EventInput } from "@/lib/adminTypes";
import { EVENT_CATEGORIES } from "@/lib/categories";
import type { CampusEvent, EventCategory } from "@/lib/types";
import { messageOf } from "../_components/useLoad";
import { Banner, Button, Field, Modal, inputClass } from "../_components/ui";

const DEPARTMENTS = [
  "Information Science and Engineering",
  "Computer Science and Engineering",
  "Electronics and Communication Engineering",
  "Electrical and Electronics Engineering",
  "Mechanical Engineering",
];

interface FormState {
  name: string;
  category: EventCategory;
  date: string;
  time: string;
  duration: string;
  venue: string;
  capacity: string;
  organizer: string;
  description: string;
  tags: string;
  department: string;
}

function initial(event: CampusEvent | null, department: string | null): FormState {
  if (!event) {
    return {
      name: "",
      category: "artificial-intelligence",
      date: "",
      time: "",
      duration: "60",
      venue: "",
      capacity: "50",
      organizer: "",
      description: "",
      tags: "",
      department: department ?? "",
    };
  }
  return {
    name: event.name,
    category: event.category,
    date: event.date,
    time: event.time,
    duration: String(event.duration_minutes),
    venue: event.venue,
    capacity: String(event.capacity),
    organizer: event.organizer,
    description: event.description,
    tags: event.tags.join(", "),
    department: event.department ?? "",
  };
}

// Create or edit an event. A faculty member's events always belong to their own
// department, so only an administrator can choose one.
export default function EventForm({
  event,
  isAdmin,
  ownDepartment,
  onClose,
  onSaved,
}: {
  event: CampusEvent | null;
  isAdmin: boolean;
  ownDepartment: string | null;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [form, setForm] = useState(() => initial(event, ownDepartment));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const set =
    <K extends keyof FormState>(key: K) =>
    (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) =>
      setForm((current) => ({ ...current, [key]: e.target.value as FormState[K] }));

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    const input: EventInput = {
      name: form.name,
      category: form.category,
      date: form.date,
      time: form.time,
      duration_minutes: Number(form.duration),
      venue: form.venue,
      capacity: Number(form.capacity),
      organizer: form.organizer,
      description: form.description,
      tags: form.tags.split(",").map((t) => t.trim()).filter(Boolean),
      department: isAdmin ? form.department || null : null,
    };
    try {
      if (event) await updateEvent(event.id, input);
      else await createEvent(input);
      onSaved();
    } catch (err) {
      setError(messageOf(err, "Could not save the event."));
      setBusy(false);
    }
  }

  return (
    <Modal title={event ? `Edit ${event.name}` : "New event"} onClose={onClose} wide>
      <form onSubmit={submit} className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <div className="sm:col-span-2">
          <Field label="Name">
            <input required maxLength={200} value={form.name} onChange={set("name")} className={inputClass} />
          </Field>
        </div>
        <Field label="Category">
          <select value={form.category} onChange={set("category")} className={inputClass}>
            {EVENT_CATEGORIES.map((c) => (
              <option key={c.value} value={c.value}>
                {c.label}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Organiser">
          <input required maxLength={200} value={form.organizer} onChange={set("organizer")} className={inputClass} />
        </Field>
        <Field label="Date">
          <input required type="date" value={form.date} onChange={set("date")} className={inputClass} />
        </Field>
        <Field label="Start time">
          <input required type="time" value={form.time} onChange={set("time")} className={inputClass} />
        </Field>
        <Field label="Duration (minutes)">
          <input required type="number" min={1} max={1440} value={form.duration} onChange={set("duration")} className={inputClass} />
        </Field>
        <Field
          label="Capacity"
          hint={event ? `${event.registered} seats are taken; capacity cannot go below that.` : undefined}
        >
          <input required type="number" min={event ? Math.max(1, event.registered) : 1} value={form.capacity} onChange={set("capacity")} className={inputClass} />
        </Field>
        <div className="sm:col-span-2">
          <Field label="Venue">
            <input required maxLength={200} value={form.venue} onChange={set("venue")} className={inputClass} />
          </Field>
        </div>
        <div className="sm:col-span-2">
          <Field label="Description">
            <textarea required rows={4} maxLength={5000} value={form.description} onChange={set("description")} className={inputClass} />
          </Field>
        </div>
        <div className="sm:col-span-2">
          <Field label="Tags" hint="Separate with commas.">
            <input value={form.tags} onChange={set("tags")} className={inputClass} />
          </Field>
        </div>
        {isAdmin ? (
          <div className="sm:col-span-2">
            <Field label="Department" hint="Faculty of this department can edit the event. Leave empty for a campus-wide event.">
              <select value={form.department} onChange={set("department")} className={inputClass}>
                <option value="">Campus-wide</option>
                {DEPARTMENTS.map((d) => (
                  <option key={d} value={d}>
                    {d}
                  </option>
                ))}
              </select>
            </Field>
          </div>
        ) : (
          ownDepartment && (
            <p className="text-small text-muted sm:col-span-2">
              This event will belong to {ownDepartment}.
            </p>
          )
        )}
        {error && (
          <div className="sm:col-span-2">
            <Banner kind="error">{error}</Banner>
          </div>
        )}
        <div className="flex justify-end gap-2 sm:col-span-2">
          <Button onClick={onClose} disabled={busy}>
            Cancel
          </Button>
          <Button kind="primary" type="submit" disabled={busy}>
            {busy ? "Saving…" : event ? "Save changes" : "Create event"}
          </Button>
        </div>
      </form>
    </Modal>
  );
}
