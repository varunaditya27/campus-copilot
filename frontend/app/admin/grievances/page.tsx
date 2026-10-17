"use client";

import { useCallback, useState } from "react";
import { listGrievances, updateGrievance } from "@/lib/adminApi";
import type { Grievance, GrievanceStatus } from "@/lib/adminTypes";
import { messageOf, useLoad } from "../_components/useLoad";
import { Banner, Button, Field, Loading, Modal, PageHeader, formatDateTime, inputClass } from "../_components/ui";

const COLUMNS: { status: GrievanceStatus; title: string }[] = [
  { status: "open", title: "Open" },
  { status: "in_progress", title: "In progress" },
  { status: "resolved", title: "Resolved" },
];

const STATUS_LABEL: Record<GrievanceStatus, string> = {
  open: "Open",
  in_progress: "In progress",
  resolved: "Resolved",
};

interface Move {
  ticket: Grievance;
  status: GrievanceStatus;
}

export default function GrievancesPage() {
  const load = useCallback(() => listGrievances(), []);
  const { data, error, reload, setData } = useLoad(load, "Could not load grievances.");
  const [notice, setNotice] = useState<string | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  const [move, setMove] = useState<Move | null>(null);
  const [dragging, setDragging] = useState<number | null>(null);
  const [over, setOver] = useState<GrievanceStatus | null>(null);

  const tickets = data?.tickets ?? [];

  // Show a ticket in its new column straight away, and put it back if the server refuses.
  async function apply(ticket: Grievance, status: GrievanceStatus, note: string | null): Promise<string | null> {
    const previous = data;
    setData((current) =>
      current
        ? {
            ...current,
            tickets: current.tickets.map((t) => (t.id === ticket.id ? { ...t, status, resolution_note: note } : t)),
          }
        : current,
    );
    try {
      await updateGrievance(ticket.id, status, note);
      setNotice(`${ticket.ticket} is now ${STATUS_LABEL[status].toLowerCase()}.${ticket.status !== status ? " The student was emailed if mail is set up." : ""}`);
      reload();
      return null;
    } catch (err) {
      setData(previous);
      return messageOf(err, "Could not update the ticket.");
    }
  }

  async function request(ticket: Grievance, status: GrievanceStatus) {
    setProblem(null);
    setNotice(null);
    if (ticket.status === status) return;
    if (status === "resolved") {
      setMove({ ticket, status }); // the student is told the outcome, so a note is needed
      return;
    }
    const failure = await apply(ticket, status, ticket.resolution_note);
    if (failure) setProblem(failure);
  }

  return (
    <div className="space-y-6">
      <PageHeader title="Grievances" />
      <p className="max-w-2xl text-small text-muted">
        Drag a ticket to another column, or use the menu on the card. Resolving needs a note: the student is emailed the
        outcome. Anything involving ragging, harassment or safety never reaches this board; it is sent to the proper
        committee instead.
      </p>
      {notice && <Banner kind="success">{notice}</Banner>}
      {(problem || error) && <Banner kind="error">{problem ?? error}</Banner>}
      {!error && !data && <Loading what="grievances" />}

      {data && (
        <div className="grid gap-4 lg:grid-cols-3">
          {COLUMNS.map((column) => {
            const inColumn = tickets.filter((t) => t.status === column.status);
            return (
              <section
                key={column.status}
                aria-label={`${column.title} tickets`}
                onDragOver={(e) => {
                  e.preventDefault();
                  setOver(column.status);
                }}
                onDragLeave={() => setOver((current) => (current === column.status ? null : current))}
                onDrop={(e) => {
                  e.preventDefault();
                  setOver(null);
                  const ticket = tickets.find((t) => t.id === dragging);
                  setDragging(null);
                  if (ticket) void request(ticket, column.status);
                }}
                className={`min-h-48 p-3 transition-colors duration-150 ${over === column.status ? "bg-ink/10 outline-2 outline-ink" : "bg-surface"}`}
              >
                <h2 className="mb-3 flex items-center justify-between text-small text-muted">
                  {column.title}
                  <span className="bg-surface px-2 py-0.5 text-ink">{inColumn.length}</span>
                </h2>
                <ul className="space-y-2">
                  {inColumn.map((t) => (
                    <li
                      key={t.id}
                      draggable
                      onDragStart={() => setDragging(t.id)}
                      onDragEnd={() => setDragging(null)}
                      className={`cursor-grab bg-ground p-3 ${dragging === t.id ? "opacity-50" : ""}`}
                    >
                      <div className="flex items-start justify-between gap-2">
                        <span className="text-small font-medium tabular-nums text-ink">{t.ticket}</span>
                        <span className="text-small text-muted">{t.category}</span>
                      </div>
                      <button
                        type="button"
                        onClick={() => setMove({ ticket: t, status: t.status })}
                        className="mt-1 block w-full text-left text-small text-ink hover:underline"
                      >
                        <span className="line-clamp-3">{t.description}</span>
                      </button>
                      <p className="mt-2 text-small text-muted">
                        {t.student_name} · {formatDateTime(t.submitted)}
                      </p>
                      <select
                        aria-label={`Move ${t.ticket}`}
                        value={t.status}
                        onChange={(e) => void request(t, e.target.value as GrievanceStatus)}
                        className="mt-2 w-full border border-muted bg-ground px-2 py-1.5 text-small text-ink"
                      >
                        {COLUMNS.map((c) => (
                          <option key={c.status} value={c.status}>
                            {c.title}
                          </option>
                        ))}
                      </select>
                    </li>
                  ))}
                  {inColumn.length === 0 && <li className="px-1 py-4 text-center text-small text-muted">Nothing here.</li>}
                </ul>
              </section>
            );
          })}
        </div>
      )}

      {move && (
        <TicketDialog
          key={`${move.ticket.id}-${move.status}`}
          ticket={move.ticket}
          initialStatus={move.status}
          onClose={() => setMove(null)}
          onSave={async (status, note) => {
            const failure = await apply(move.ticket, status, note);
            if (!failure) setMove(null);
            return failure;
          }}
        />
      )}
    </div>
  );
}

function TicketDialog({
  ticket,
  initialStatus,
  onClose,
  onSave,
}: {
  ticket: Grievance;
  initialStatus: GrievanceStatus;
  onClose: () => void;
  onSave: (status: GrievanceStatus, note: string | null) => Promise<string | null>;
}) {
  const [status, setStatus] = useState(initialStatus);
  const [note, setNote] = useState(ticket.resolution_note ?? "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (status === "resolved" && !note.trim()) {
      setError("Add a resolution note: the student is told the outcome.");
      return;
    }
    setBusy(true);
    const failure = await onSave(status, note.trim() || null);
    if (failure) {
      setError(failure);
      setBusy(false);
    }
  }

  return (
    <Modal title={`${ticket.ticket}: ${ticket.category}`} onClose={onClose}>
      <p className="text-small text-muted">
        {ticket.student_name} ({ticket.student_id}), {ticket.program}. Submitted {formatDateTime(ticket.submitted)}.
      </p>
      <p className="mt-3 whitespace-pre-wrap bg-surface p-3 text-body text-ink">{ticket.description}</p>
      <form onSubmit={submit} className="mt-5 space-y-4">
        <Field label="Status">
          <select value={status} onChange={(e) => setStatus(e.target.value as GrievanceStatus)} className={inputClass}>
            {COLUMNS.map((c) => (
              <option key={c.status} value={c.status}>
                {c.title}
              </option>
            ))}
          </select>
        </Field>
        <Field label={status === "resolved" ? "Resolution note (required)" : "Note to the student (optional)"}>
          <textarea rows={4} maxLength={2000} value={note} onChange={(e) => setNote(e.target.value)} className={inputClass} />
        </Field>
        {error && <Banner kind="error">{error}</Banner>}
        <div className="flex justify-end gap-2">
          <Button onClick={onClose} disabled={busy}>
            Cancel
          </Button>
          <Button kind="primary" type="submit" disabled={busy}>
            {busy ? "Saving…" : "Save"}
          </Button>
        </div>
      </form>
    </Modal>
  );
}
