"use client";

import { useState } from "react";
import type { Source } from "@/lib/types";
import { DocumentIcon } from "../icons";

export default function SourceCard({ source }: { source: Source }) {
  const [open, setOpen] = useState(false);
  const hasSnippet = Boolean(source.snippet);

  return (
    <div className="border border-line bg-cream-raised">
      <button
        type="button"
        onClick={() => hasSnippet && setOpen((v) => !v)}
        className={`flex w-full items-center gap-2 px-2.5 py-1.5 text-left ${
          hasSnippet ? "cursor-pointer" : "cursor-default"
        }`}
        aria-expanded={open}
      >
        <DocumentIcon className="h-3.5 w-3.5 shrink-0 text-brass" />
        <span className="font-mono text-[11px] tracking-tight text-ink-soft">
          {source.document}
          {source.section && (
            <span className="text-ink-faint"> · {source.section}</span>
          )}
        </span>
      </button>
      {open && hasSnippet && (
        <p className="anim-fade rule-top border-line px-2.5 py-2 font-body text-[12.5px] leading-relaxed text-ink-soft">
          {source.snippet}
        </p>
      )}
    </div>
  );
}
