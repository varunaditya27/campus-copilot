"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { importStudents, listStudents } from "@/lib/adminApi";
import type { ImportResult } from "@/lib/adminTypes";
import { messageOf, useLoad } from "../_components/useLoad";
import { Banner, Button, Loading, PageHeader, inputClass, tableClass, tdClass, thClass } from "../_components/ui";

export default function AdminStudentsPage() {
  const [search, setSearch] = useState("");
  const [q, setQ] = useState("");
  const [program, setProgram] = useState("");
  const [year, setYear] = useState("");
  const [page, setPage] = useState(1);

  // Wait for a pause in typing before searching.
  useEffect(() => {
    const timer = setTimeout(() => {
      setQ(search.trim());
      setPage(1);
    }, 300);
    return () => clearTimeout(timer);
  }, [search]);

  const load = useCallback(() => listStudents({ page, q, program, year }), [page, q, program, year]);
  const { data, error, reload } = useLoad(load, "Could not load students.");

  const fileInput = useRef<HTMLInputElement>(null);
  const [importing, setImporting] = useState(false);
  const [importResult, setImportResult] = useState<ImportResult | null>(null);
  const [importError, setImportError] = useState<string | null>(null);

  async function onFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    setImporting(true);
    setImportError(null);
    setImportResult(null);
    try {
      setImportResult(await importStudents(file));
      reload();
    } catch (err) {
      setImportError(messageOf(err, "Could not import the file."));
    } finally {
      setImporting(false);
    }
  }

  const pages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1;

  return (
    <div className="space-y-6">
      <PageHeader title="Students">
        <input ref={fileInput} type="file" accept=".csv,text/csv" className="hidden" onChange={onFile} aria-label="CSV file to import" />
        <Button onClick={() => fileInput.current?.click()} disabled={importing}>
          {importing ? "Importing…" : "Import CSV"}
        </Button>
      </PageHeader>

      <p className="max-w-2xl text-small text-muted">
        Import adds new students from a CSV with the columns <code>student_id, name, program, year</code>. If any row is
        invalid nothing is imported, and students already on the roster are left as they are.
      </p>
      {importError && <Banner kind="error">{importError}</Banner>}
      {importResult && (
        <Banner kind="success">
          Added {importResult.created} students.
          {importResult.skipped_existing.length > 0 && ` Already on the roster and skipped: ${importResult.skipped_existing.join(", ")}.`}
        </Banner>
      )}

      <div className="flex flex-wrap gap-3">
        <input
          type="search"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search by name or student ID"
          aria-label="Search students"
          className={`${inputClass} max-w-xs`}
        />
        <select
          value={program}
          onChange={(e) => {
            setProgram(e.target.value);
            setPage(1);
          }}
          aria-label="Filter by programme"
          className={`${inputClass} max-w-xs`}
        >
          <option value="">All programmes</option>
          {data?.programs.map((p) => (
            <option key={p} value={p}>
              {p}
            </option>
          ))}
        </select>
        <select
          value={year}
          onChange={(e) => {
            setYear(e.target.value);
            setPage(1);
          }}
          aria-label="Filter by year"
          className={`${inputClass} max-w-[10rem]`}
        >
          <option value="">All years</option>
          {[1, 2, 3, 4].map((y) => (
            <option key={y} value={y}>
              Year {y}
            </option>
          ))}
        </select>
      </div>

      {error && <Banner kind="error">{error}</Banner>}
      {!error && !data && <Loading what="students" />}

      {data && (
        <>
          <div className="overflow-x-auto bg-surface">
            <table className={tableClass}>
              <thead>
                <tr>
                  <th className={thClass}>Student</th>
                  <th className={thClass}>Programme</th>
                  <th className={thClass}>Year</th>
                  <th className={thClass}>Account</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((s) => (
                  <tr key={s.student_id}>
                    <td className={tdClass}>
                      <Link href={`/admin/students/${s.student_id}`} className="font-medium underline underline-offset-2 hover:decoration-2">
                        {s.name}
                      </Link>
                      <div className="text-small tabular-nums text-muted">{s.student_id}</div>
                    </td>
                    <td className={tdClass}>{s.program}</td>
                    <td className={tdClass}>{s.year}</td>
                    <td className={`${tdClass} text-muted`}>{s.has_account ? "Signed up" : "No account"}</td>
                  </tr>
                ))}
                {data.items.length === 0 && (
                  <tr>
                    <td className={`${tdClass} text-muted`} colSpan={4}>
                      No students match.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
          <div className="flex items-center justify-between text-small tabular-nums text-muted">
            <span>
              {data.total} students · page {data.page} of {pages}
            </span>
            <span className="flex gap-2">
              <Button onClick={() => setPage(page - 1)} disabled={page <= 1}>
                Previous
              </Button>
              <Button onClick={() => setPage(page + 1)} disabled={page >= pages}>
                Next
              </Button>
            </span>
          </div>
        </>
      )}
    </div>
  );
}
