"use client";

import { useState } from "react";
import type { Source } from "@/lib/types";
import { DocumentIcon } from "../icons";

export default function SourceCard({ source }: { source: Source }) {
  const [open, setOpen] = useState(false);
  const hasSnippet = Boolean(source.snippet);

  return (
    <div className="bg-surface">
      <button
        type="button"
        onClick={() => hasSnippet && setOpen((v) => !v)}
        className={`flex w-full items-center gap-2 px-2.5 py-1.5 text-left ${
          hasSnippet ? "cursor-pointer" : "cursor-default"
        }`}
        aria-expanded={open}
      >
        <DocumentIcon className="h-3.5 w-3.5 shrink-0 text-accent" />
        <span className="text-small text-ink">
          {source.document}
          {source.section && (
            <span className="text-muted"> · {source.section}</span>
          )}
        </span>
      </button>
      {open && hasSnippet && (
        <p className="anim-fade px-2.5 pb-2 text-small leading-relaxed text-ink">
          {source.snippet}
        </p>
      )}
    </div>
  );
}
