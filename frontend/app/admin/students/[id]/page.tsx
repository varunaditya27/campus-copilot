"use client";

import Link from "next/link";
import { use, useCallback } from "react";
import { getStudent } from "@/lib/adminApi";
import { useLoad } from "../../_components/useLoad";
import { Banner, Loading, PageHeader, tableClass, tdClass, thClass } from "../../_components/ui";

export default function StudentDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const load = useCallback(() => getStudent(id), [id]);
  const { data: student, error } = useLoad(load, "Could not load this student.");

  const semesters = student ? [...new Set(student.records.map((r) => r.semester))] : [];

  return (
    <div className="space-y-6">
      <Link href="/admin/students" className="text-small text-muted hover:text-ink">
        ← All students
      </Link>
      {error && <Banner kind="error">{error}</Banner>}
      {!error && !student && <Loading what="the student" />}

      {student && (
        <>
          <PageHeader note={student.student_id} title={student.name} />
          <dl className="grid grid-cols-2 gap-x-8 gap-y-5 bg-surface p-6 sm:grid-cols-4">
            {[
              ["Programme", student.program],
              ["Year", String(student.year)],
              ["Semester", `${student.semester}${student.section ? ` (section ${student.section})` : ""}`],
              ["CGPA", student.cgpa === null ? "No results yet" : String(student.cgpa)],
              ["Account", student.account ? `${student.account.email}${student.account.active ? "" : " (disabled)"}` : "No account"],
              ["Backlogs", student.backlogs.length ? student.backlogs.map((b) => b.course_code).join(", ") : "None"],
              ["Interests", student.interests.length ? student.interests.join(", ") : "None given"],
            ].map(([label, value]) => (
              <div key={label}>
                <dt className="text-small text-muted">{label}</dt>
                <dd className="mt-1 text-body text-ink">{value}</dd>
              </div>
            ))}
          </dl>

          <section>
            <h2 className="text-xl font-medium">Academic records</h2>
            {student.records.length === 0 && <p className="mt-2 text-small text-muted">No records.</p>}
            {semesters.map((semester) => (
              <div key={semester} className="mt-4 overflow-x-auto bg-surface">
                <table className={tableClass}>
                  <caption className="px-3 pt-3 pb-1 text-left text-small font-medium text-ink">
                    Semester {semester}
                  </caption>
                  <thead>
                    <tr>
                      <th className={thClass}>Course</th>
                      <th className={thClass}>Credits</th>
                      <th className={thClass}>Attendance</th>
                      <th className={thClass}>Grade</th>
                    </tr>
                  </thead>
                  <tbody>
                    {student.records
                      .filter((r) => r.semester === semester)
                      .map((r) => (
                        <tr key={r.course_code}>
                          <td className={tdClass}>
                            {r.course}
                            <div className="text-small tabular-nums text-muted">{r.course_code}</div>
                          </td>
                          <td className={tdClass}>{r.credits}</td>
                          <td className={tdClass}>
                            {r.attended}/{r.total} ({r.total ? Math.round((100 * r.attended) / r.total) : 0}%)
                          </td>
                          <td className={tdClass}>{r.grade ?? "Pending"}</td>
                        </tr>
                      ))}
                  </tbody>
                </table>
              </div>
            ))}
          </section>

          <div className="grid gap-6 lg:grid-cols-2">
            <section>
              <h2 className="text-xl font-medium">Event registrations</h2>
              <ul className="mt-3 flex flex-col gap-0.5">
                {student.registrations.map((r) => (
                  <li key={r.registration_id} className="bg-surface px-3 py-2.5 text-small">
                    <Link href={`/admin/events/${r.event_id}`} className="underline underline-offset-2 hover:decoration-2">
                      {r.event}
                    </Link>
                    <span className="ml-2 text-muted">{r.date}</span>
                  </li>
                ))}
                {student.registrations.length === 0 && <li className="bg-surface px-3 py-2.5 text-small text-muted">None.</li>}
              </ul>
            </section>
            <section>
              <h2 className="text-xl font-medium">Grievance tickets</h2>
              <ul className="mt-3 flex flex-col gap-0.5">
                {student.tickets.map((t) => (
                  <li key={t.ticket} className="bg-surface px-3 py-2.5 text-small">
                    <span className="text-small tabular-nums">{t.ticket}</span> · {t.category} · {t.status.replace("_", " ")}
                    <span className="ml-2 text-muted">{t.submitted}</span>
                  </li>
                ))}
                {student.tickets.length === 0 && <li className="bg-surface px-3 py-2.5 text-small text-muted">None.</li>}
              </ul>
            </section>
          </div>
        </>
      )}
    </div>
  );
}
