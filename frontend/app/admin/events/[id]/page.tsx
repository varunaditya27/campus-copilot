"use client";

import Link from "next/link";
import { use, useCallback, useState } from "react";
import { exportRegistrations, getEventRoster } from "@/lib/adminApi";
import { formatDateTime, Banner, Button, Gauge, Loading, PageHeader, tableClass, tdClass, thClass } from "../../_components/ui";
import { messageOf, useLoad } from "../../_components/useLoad";

export default function EventRosterPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const load = useCallback(() => getEventRoster(id), [id]);
  const { data: roster, error } = useLoad(load, "Could not load this event.");
  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState<string | null>(null);

  async function download() {
    setExporting(true);
    setExportError(null);
    try {
      const blob = await exportRegistrations(id);
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `registrations-${id}.csv`;
      link.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setExportError(messageOf(err, "Could not export the registrations."));
    } finally {
      setExporting(false);
    }
  }

  return (
    <div className="space-y-6">
      <Link href="/admin/events" className="font-mono text-[11px] uppercase tracking-[0.14em] text-ink-faint hover:text-ink">
        ← All events
      </Link>
      {error && <Banner kind="error">{error}</Banner>}
      {!error && !roster && <Loading what="the roster" />}

      {roster && (
        <>
          <PageHeader eyebrow={roster.event.category} title={roster.event.name}>
            <Button onClick={download} disabled={exporting || roster.registrations.length === 0}>
              {exporting ? "Exporting…" : "Export CSV"}
            </Button>
          </PageHeader>
          {exportError && <Banner kind="error">{exportError}</Banner>}

          <div className="grid gap-6 border-y border-line py-6 sm:grid-cols-3">
            <div>
              <p className="font-mono text-[11px] uppercase tracking-[0.14em] text-ink-faint">When</p>
              <p className="mt-1 text-[15px]">
                {roster.event.date} at {roster.event.time}
              </p>
              <p className="text-[13px] text-ink-soft">{roster.event.duration_minutes} minutes</p>
            </div>
            <div>
              <p className="font-mono text-[11px] uppercase tracking-[0.14em] text-ink-faint">Where</p>
              <p className="mt-1 text-[15px]">{roster.event.venue}</p>
              <p className="text-[13px] text-ink-soft">{roster.event.organizer}</p>
            </div>
            <div>
              <p className="font-mono text-[11px] uppercase tracking-[0.14em] text-ink-faint">Capacity</p>
              <div className="mt-2">
                <Gauge value={roster.event.registered} max={roster.event.capacity} label="Seats taken" />
              </div>
            </div>
          </div>

          <section>
            <h2 className="font-display text-xl font-medium">Registered ({roster.registrations.length})</h2>
            <div className="mt-3 overflow-x-auto border border-line bg-cream-raised">
              <table className={tableClass}>
                <thead>
                  <tr>
                    <th className={thClass}>Student</th>
                    <th className={thClass}>Programme</th>
                    <th className={thClass}>Year</th>
                    <th className={thClass}>Registration</th>
                    <th className={thClass}>Registered at</th>
                  </tr>
                </thead>
                <tbody>
                  {roster.registrations.map((r) => (
                    <tr key={r.registration_id}>
                      <td className={tdClass}>
                        {r.student_name}
                        <div className="font-mono text-[11px] text-ink-faint">{r.student_id}</div>
                      </td>
                      <td className={tdClass}>{r.program}</td>
                      <td className={tdClass}>{r.year}</td>
                      <td className={`${tdClass} font-mono text-[12px]`}>{r.registration_id}</td>
                      <td className={`${tdClass} whitespace-nowrap`}>{formatDateTime(r.registered_at)}</td>
                    </tr>
                  ))}
                  {roster.registrations.length === 0 && (
                    <tr>
                      <td className={`${tdClass} text-ink-faint`} colSpan={5}>
                        Nobody has registered yet.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </section>

          {roster.waitlist.length > 0 && (
            <section>
              <h2 className="font-display text-xl font-medium">Waitlist ({roster.waitlist.length})</h2>
              <div className="mt-3 overflow-x-auto border border-line bg-cream-raised">
                <table className={tableClass}>
                  <thead>
                    <tr>
                      <th className={thClass}>Place</th>
                      <th className={thClass}>Student</th>
                      <th className={thClass}>Programme</th>
                      <th className={thClass}>Year</th>
                    </tr>
                  </thead>
                  <tbody>
                    {roster.waitlist.map((w) => (
                      <tr key={w.student_id}>
                        <td className={tdClass}>{w.position}</td>
                        <td className={tdClass}>
                          {w.student_name}
                          <div className="font-mono text-[11px] text-ink-faint">{w.student_id}</div>
                        </td>
                        <td className={tdClass}>{w.program}</td>
                        <td className={tdClass}>{w.year}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          )}
        </>
      )}
    </div>
  );
}
