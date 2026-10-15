"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { deleteDocument, getDocumentChunks, getKnowledgeStatus, runIngest, uploadDocument } from "@/lib/adminApi";
import type { DocumentChunks } from "@/lib/adminTypes";
import { messageOf, useLoad } from "../_components/useLoad";
import { Banner, Button, ConfirmDialog, Loading, Modal, PageHeader, formatDateTime, tableClass, tdClass, thClass } from "../_components/ui";

function useElapsed(running: boolean): number {
  const [seconds, setSeconds] = useState(0);
  useEffect(() => {
    if (!running) return;
    const started = Date.now();
    const timer = setInterval(() => setSeconds(Math.floor((Date.now() - started) / 1000)), 500);
    return () => {
      clearInterval(timer);
      setSeconds(0);
    };
  }, [running]);
  return seconds;
}

export default function AdminKnowledgePage() {
  const load = useCallback(() => getKnowledgeStatus(), []);
  const { data: status, error, reload } = useLoad(load, "Could not load the knowledge base.");

  const fileInput = useRef<HTMLInputElement>(null);
  const [working, setWorking] = useState<null | "upload" | "ingest" | "rebuild">(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  const elapsed = useElapsed(working === "ingest" || working === "rebuild");

  const [preview, setPreview] = useState<DocumentChunks | null>(null);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [removing, setRemoving] = useState<string | null>(null);
  const [removeError, setRemoveError] = useState<string | null>(null);

  async function onFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    setWorking("upload");
    setProblem(null);
    setNotice(null);
    try {
      const result = await uploadDocument(file);
      setNotice(`${result.replaced ? "Replaced" : "Added"} ${result.document}: ${result.chunks} chunks.`);
      reload();
    } catch (err) {
      setProblem(messageOf(err, "Could not upload the file."));
    } finally {
      setWorking(null);
    }
  }

  async function ingest(full: boolean) {
    setWorking(full ? "rebuild" : "ingest");
    setProblem(null);
    setNotice(null);
    try {
      await runIngest(full);
      setNotice(full ? "Rebuilt the whole knowledge base." : "Knowledge base is up to date.");
      reload();
    } catch (err) {
      setProblem(messageOf(err, "The ingest failed."));
    } finally {
      setWorking(null);
    }
  }

  async function open(name: string) {
    setPreviewError(null);
    try {
      setPreview(await getDocumentChunks(name));
    } catch (err) {
      setPreviewError(messageOf(err, "Could not load the chunks."));
    }
  }

  async function remove() {
    if (!removing) return;
    setRemoveError(null);
    try {
      await deleteDocument(removing);
      setNotice(`Removed ${removing}.`);
      setRemoving(null);
      reload();
    } catch (err) {
      setRemoveError(messageOf(err, "Could not remove the document."));
    }
  }

  const ingesting = working === "ingest" || working === "rebuild";

  return (
    <div className="space-y-6">
      <PageHeader eyebrow="Dashboard" title="Knowledge base">
        <input ref={fileInput} type="file" accept=".md,.pdf" className="hidden" onChange={onFile} aria-label="Document to upload" />
        <Button onClick={() => fileInput.current?.click()} disabled={working !== null}>
          {working === "upload" ? "Uploading…" : "Upload document"}
        </Button>
        <Button onClick={() => ingest(false)} disabled={working !== null}>
          Re-ingest
        </Button>
        <Button onClick={() => ingest(true)} disabled={working !== null}>
          Full rebuild
        </Button>
      </PageHeader>

      {ingesting && (
        <div role="status" aria-live="polite" className="border border-line bg-cream-raised px-4 py-3">
          <p className="font-mono text-[12px] text-ink-soft">
            {working === "rebuild" ? "Rebuilding everything" : "Checking which documents changed"}… {elapsed}s. This
            can take a minute: documents are split and embedded one by one.
          </p>
          <div className="mt-2 h-1.5 w-full overflow-hidden bg-cream-sunken">
            <div className="h-full w-1/3 animate-pulse bg-brass" />
          </div>
        </div>
      )}
      {notice && <Banner kind="success">{notice}</Banner>}
      {(problem || error) && <Banner kind="error">{problem ?? error}</Banner>}
      {previewError && <Banner kind="error">{previewError}</Banner>}
      {!error && !status && <Loading what="the knowledge base" />}

      {status && (
        <>
          <p className="text-[13px] text-ink-soft">
            {status.built
              ? `${status.document_count} documents, ${status.chunk_count} chunks in "${status.collection}". Last ingested ${status.last_ingested_at ? formatDateTime(status.last_ingested_at) : "never"}.`
              : "The knowledge base has not been built yet. Run an ingest."}
          </p>
          <div className="overflow-x-auto border border-line bg-cream-raised">
            <table className={tableClass}>
              <thead>
                <tr>
                  <th className={thClass}>Document</th>
                  <th className={thClass}>Source</th>
                  <th className={thClass}>Chunks</th>
                  <th className={thClass}>Last updated</th>
                  <th className={thClass}>
                    <span className="sr-only">Actions</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {status.documents.map((d) => (
                  <tr key={d.document}>
                    <td className={`${tdClass} font-medium`}>{d.document}</td>
                    <td className={`${tdClass} text-ink-soft`}>{d.source}</td>
                    <td className={tdClass}>{d.chunks}</td>
                    <td className={`${tdClass} whitespace-nowrap`}>{d.ingested_at ? formatDateTime(d.ingested_at) : "—"}</td>
                    <td className={`${tdClass} whitespace-nowrap text-right`}>
                      <span className="inline-flex gap-2">
                        <Button onClick={() => open(d.document)} aria-label={`Preview ${d.document}`}>
                          Preview
                        </Button>
                        {d.source === "uploaded" && (
                          <Button onClick={() => setRemoving(d.document)} aria-label={`Remove ${d.document}`}>
                            Remove
                          </Button>
                        )}
                      </span>
                    </td>
                  </tr>
                ))}
                {status.documents.length === 0 && (
                  <tr>
                    <td className={`${tdClass} text-ink-faint`} colSpan={5}>
                      No documents.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </>
      )}

      {preview && (
        <Modal title={preview.document} onClose={() => setPreview(null)} wide>
          <p className="text-[13px] text-ink-soft">
            {preview.chunk_count} chunks · embedded with <strong>{preview.embedding.model}</strong> (
            {preview.embedding.dimensions}-dimensional vectors) in collection {preview.embedding.collection}
            {preview.ingested_at && ` · ingested ${formatDateTime(preview.ingested_at)}`}.
          </p>
          <ol className="mt-4 max-h-[60vh] space-y-3 overflow-y-auto pr-1">
            {preview.chunks.map((c) => (
              <li key={c.id} className="border border-line bg-cream-raised p-3">
                <p className="font-mono text-[11px] text-ink-faint">
                  {c.id} · {c.section} · {c.characters} characters, {c.words} words
                </p>
                <p className="mt-1.5 whitespace-pre-wrap text-[13.5px] text-ink">{c.text}</p>
              </li>
            ))}
          </ol>
        </Modal>
      )}

      {removing && (
        <ConfirmDialog title={`Remove ${removing}?`} confirmLabel="Remove" busy={false} error={removeError} onConfirm={remove} onCancel={() => setRemoving(null)}>
          <p>The document and its chunks are removed, so the assistant can no longer find what it said. Curated documents cannot be removed here.</p>
        </ConfirmDialog>
      )}
    </div>
  );
}
