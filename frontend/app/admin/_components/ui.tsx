"use client";

import { useEffect, useRef } from "react";

export function PageHeader({
  title,
  note,
  children,
}: {
  title: string;
  note?: string;
  children?: React.ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 className="text-3xl font-medium tracking-[-0.03em] text-balance text-ink">{title}</h1>
        {note && <p className="mt-1 text-body text-muted first-letter:uppercase">{note}</p>}
      </div>
      {children && <div className="flex flex-wrap items-center gap-2">{children}</div>}
    </div>
  );
}

type ButtonKind = "primary" | "secondary" | "danger";

const BUTTON_STYLES: Record<ButtonKind, string> = {
  primary: "bg-accent text-accent-ink",
  secondary: "bg-ink/10 text-ink hover:bg-ink hover:text-ground",
  danger: "bg-danger text-ground",
};

export function Button({
  kind = "secondary",
  className = "",
  ...props
}: { kind?: ButtonKind } & React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      type="button"
      {...props}
      className={`min-h-10 px-4 py-2 text-small font-medium transition duration-150 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink active:scale-[0.98] disabled:opacity-50 ${BUTTON_STYLES[kind]} ${className}`}
    />
  );
}

export function Banner({
  kind,
  children,
}: {
  kind: "error" | "success" | "info";
  children: React.ReactNode;
}) {
  const styles = {
    error: "bg-danger/10 text-danger",
    success: "bg-surface text-ink",
    info: "bg-surface text-ink",
  }[kind];
  return (
    <p role={kind === "error" ? "alert" : "status"} className={`px-4 py-2.5 text-small ${styles}`}>
      {children}
    </p>
  );
}

export function Loading({ what }: { what: string }) {
  return <p className="text-small text-muted">Loading {what}…</p>;
}

export function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <label className="block">
      <span className="text-small font-medium text-ink">{label}</span>
      <div className="mt-1.5">{children}</div>
      {hint && <span className="mt-1 block text-small text-muted">{hint}</span>}
    </label>
  );
}

export const inputClass =
  "w-full border border-muted bg-ground px-3 py-2 text-body text-ink placeholder:text-muted focus:outline-2 focus:outline-offset-2 focus:outline-ink";

export const tableClass = "w-full border-collapse text-left text-small tabular-nums";
export const thClass =
  "border-b border-muted px-3 py-2 font-medium text-muted";
export const tdClass = "border-b border-ground px-3 py-2.5 align-top";

// A bar showing how much of a total is used.
export function Gauge({
  value,
  max,
  label,
}: {
  value: number;
  max: number;
  label: string;
}) {
  const share = max > 0 ? Math.min(100, Math.round((100 * value) / max)) : 0;
  const colour = share >= 100 ? "bg-danger" : share >= 80 ? "bg-ink" : "bg-muted";
  return (
    <div>
      <div
        role="meter"
        aria-label={label}
        aria-valuemin={0}
        aria-valuemax={max}
        aria-valuenow={value}
        className="h-2 w-full bg-ground"
      >
        <div className={`h-full ${colour}`} style={{ width: `${share}%` }} />
      </div>
      <p className="mt-1 text-small text-muted tabular-nums">
        {value} / {max} ({share}%)
      </p>
    </div>
  );
}

export function Modal({
  title,
  onClose,
  children,
  wide = false,
}: {
  title: string;
  onClose: () => void;
  children: React.ReactNode;
  wide?: boolean;
}) {
  const panel = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    panel.current?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("keydown", onKey);
      previous?.focus();
    };
  }, [onClose]);

  return (
    <div
      className="anim-fade fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-ink/50 px-4 py-10"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        ref={panel}
        tabIndex={-1}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className={`anim-rise w-full bg-ground p-6 shadow-2xl outline-none ${wide ? "max-w-3xl" : "max-w-lg"}`}
      >
        <div className="flex items-start justify-between gap-4">
          <h2 className="text-xl font-medium text-ink">{title}</h2>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="-mt-2 -mr-2 flex h-11 w-11 shrink-0 items-center justify-center text-2xl leading-none text-muted hover:text-ink"
          >
            ×
          </button>
        </div>
        <div className="mt-4">{children}</div>
      </div>
    </div>
  );
}

export function ConfirmDialog({
  title,
  confirmLabel,
  busy,
  error,
  onConfirm,
  onCancel,
  children,
}: {
  title: string;
  confirmLabel: string;
  busy: boolean;
  error: string | null;
  onConfirm: () => void;
  onCancel: () => void;
  children: React.ReactNode;
}) {
  return (
    <Modal title={title} onClose={onCancel}>
      <div className="space-y-3 text-body text-ink">{children}</div>
      {error && (
        <div className="mt-3">
          <Banner kind="error">{error}</Banner>
        </div>
      )}
      <div className="mt-5 flex justify-end gap-2">
        <Button onClick={onCancel} disabled={busy}>
          Cancel
        </Button>
        <Button kind="danger" onClick={onConfirm} disabled={busy}>
          {busy ? "Working…" : confirmLabel}
        </Button>
      </div>
    </Modal>
  );
}

export function formatDateTime(iso: string): string {
  const date = new Date(iso);
  return Number.isNaN(date.getTime())
    ? iso
    : date.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}
