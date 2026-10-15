"use client";

import Link from "next/link";
import { useCallback, useState } from "react";
import { deleteEvent } from "@/lib/adminApi";
import { ApiError, listEvents } from "@/lib/api";
import type { CampusEvent } from "@/lib/types";
import { useAuth } from "../../components/auth/AuthProvider";
import { messageOf, useLoad } from "../_components/useLoad";
import { Banner, Button, ConfirmDialog, Gauge, Loading, PageHeader, tableClass, tdClass, thClass } from "../_components/ui";
import EventForm from "./EventForm";

export default function AdminEventsPage() {
  const { state } = useAuth();
  const user = state.status === "signedIn" ? state.user : null;
  const isAdmin = user?.role === "admin";
  const ownDepartment = user?.faculty?.department ?? null;

  const load = useCallback(() => listEvents(), []);
  const { data: events, error, reload } = useLoad(load, "Could not load events.");

  const [editing, setEditing] = useState<CampusEvent | "new" | null>(null);
  const [deleting, setDeleting] = useState<CampusEvent | null>(null);
  const [warning, setWarning] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const canManage = (event: CampusEvent) => isAdmin || (!!ownDepartment && event.department === ownDepartment);

  function closeDelete() {
    setDeleting(null);
    setWarning(null);
    setDeleteError(null);
  }

  async function confirmDelete() {
    if (!deleting) return;
    setBusy(true);
    setDeleteError(null);
    try {
      const result = await deleteEvent(deleting.id, warning !== null);
      setNotice(
        result.registrations_removed
          ? `Deleted ${deleting.name} and ${result.registrations_removed} registrations.`
          : `Deleted ${deleting.name}.`,
      );
      closeDelete();
      reload();
    } catch (err) {
      if (err instanceof ApiError && err.code === "event_has_registrations") {
        setWarning(err.message);
      } else {
        setDeleteError(messageOf(err, "Could not delete the event."));
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader eyebrow="Dashboard" title="Events">
        <Button kind="primary" onClick={() => setEditing("new")}>
          New event
        </Button>
      </PageHeader>

      {notice && <Banner kind="success">{notice}</Banner>}
      {error && <Banner kind="error">{error}</Banner>}
      {!error && events === null && <Loading what="events" />}

      {events && (
        <div className="overflow-x-auto border border-line bg-cream-raised">
          <table className={tableClass}>
            <thead>
              <tr>
                <th className={thClass}>Event</th>
                <th className={thClass}>When</th>
                <th className={thClass}>Venue</th>
                <th className={`${thClass} w-44`}>Seats</th>
                <th className={thClass}>Department</th>
                <th className={thClass}>
                  <span className="sr-only">Actions</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {events.map((event) => (
                <tr key={event.id}>
                  <td className={tdClass}>
                    <Link href={`/admin/events/${event.id}`} className="font-medium text-ink underline decoration-line-strong underline-offset-2 hover:decoration-brass">
                      {event.name}
                    </Link>
                    <div className="text-[12px] text-ink-faint">{event.category}</div>
                  </td>
                  <td className={`${tdClass} whitespace-nowrap`}>
                    {event.date}
                    <div className="text-[12px] text-ink-faint">{event.time}</div>
                  </td>
                  <td className={tdClass}>{event.venue}</td>
                  <td className={tdClass}>
                    <Gauge value={event.registered} max={event.capacity} label={`Seats taken for ${event.name}`} />
                  </td>
                  <td className={`${tdClass} text-ink-soft`}>{event.department ?? "Campus-wide"}</td>
                  <td className={`${tdClass} whitespace-nowrap text-right`}>
                    {canManage(event) ? (
                      <span className="inline-flex gap-2">
                        <Button onClick={() => setEditing(event)} aria-label={`Edit ${event.name}`}>
                          Edit
                        </Button>
                        <Button onClick={() => setDeleting(event)} aria-label={`Delete ${event.name}`}>
                          Delete
                        </Button>
                      </span>
                    ) : (
                      <span className="text-[12px] text-ink-faint">{event.department ? "Other department" : "Admin only"}</span>
                    )}
                  </td>
                </tr>
              ))}
              {events.length === 0 && (
                <tr>
                  <td className={`${tdClass} text-ink-faint`} colSpan={6}>
                    No events yet.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {editing && (
        <EventForm
          event={editing === "new" ? null : editing}
          isAdmin={isAdmin}
          ownDepartment={ownDepartment}
          onClose={() => setEditing(null)}
          onSaved={() => {
            setNotice(editing === "new" ? "Event created." : "Event saved.");
            setEditing(null);
            reload();
          }}
        />
      )}

      {deleting && (
        <ConfirmDialog
          title={`Delete ${deleting.name}?`}
          confirmLabel={warning ? "Delete event and registrations" : "Delete event"}
          busy={busy}
          error={deleteError}
          onConfirm={confirmDelete}
          onCancel={closeDelete}
        >
          {warning ? (
            <p>
              <strong className="text-rust">{warning}</strong>
            </p>
          ) : (
            <p>This removes the event from the campus listing. It cannot be undone.</p>
          )}
        </ConfirmDialog>
      )}
    </div>
  );
}
