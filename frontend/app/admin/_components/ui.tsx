"use client";

import { useEffect, useRef } from "react";

export function PageHeader({
  eyebrow,
  title,
  children,
}: {
  eyebrow: string;
  title: string;
  children?: React.ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-4">
      <div>
        <p className="font-mono text-[11px] uppercase tracking-[0.16em] text-brass">
          {eyebrow}
        </p>
        <h1 className="mt-2 font-display text-3xl font-medium tracking-tight text-ink">
          {title}
        </h1>
      </div>
      {children && <div className="flex flex-wrap items-center gap-2">{children}</div>}
    </div>
  );
}

type ButtonKind = "primary" | "secondary" | "danger";

const BUTTON_STYLES: Record<ButtonKind, string> = {
  primary: "bg-navy text-cream hover:bg-brass",
  secondary: "border border-line-strong bg-cream-raised text-ink hover:border-brass",
  danger: "bg-rust text-cream hover:bg-navy",
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
      className={`px-3.5 py-2 font-mono text-[12px] uppercase tracking-[0.1em] transition-colors duration-150 disabled:opacity-50 ${BUTTON_STYLES[kind]} ${className}`}
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
    error: "border-rust/40 bg-rust/5 text-rust",
    success: "border-forest/40 bg-forest/5 text-forest",
    info: "border-line bg-cream-raised text-ink-soft",
  }[kind];
  return (
    <p role={kind === "error" ? "alert" : "status"} className={`border px-4 py-2.5 text-[13px] ${styles}`}>
      {children}
    </p>
  );
}

export function Loading({ what }: { what: string }) {
  return <p className="font-mono text-[12px] text-ink-faint">Loading {what}…</p>;
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
      <span className="font-mono text-[11px] uppercase tracking-[0.14em] text-ink-faint">
        {label}
      </span>
      <div className="mt-1.5">{children}</div>
      {hint && <span className="mt-1 block text-[12px] text-ink-faint">{hint}</span>}
    </label>
  );
}

export const inputClass =
  "w-full border border-line-strong bg-cream-raised px-3 py-2 text-[14px] text-ink placeholder:text-ink-faint focus:border-brass focus:outline-none";

export const tableClass = "w-full border-collapse text-left text-[13.5px]";
export const thClass =
  "border-b border-line-strong px-3 py-2 font-mono text-[11px] font-medium uppercase tracking-[0.12em] text-ink-faint";
export const tdClass = "border-b border-line px-3 py-2.5 align-top";

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
  const colour = share >= 100 ? "bg-rust" : share >= 80 ? "bg-brass" : "bg-forest";
  return (
    <div>
      <div
        role="meter"
        aria-label={label}
        aria-valuemin={0}
        aria-valuemax={max}
        aria-valuenow={value}
        className="h-2 w-full bg-cream-sunken"
      >
        <div className={`h-full ${colour}`} style={{ width: `${share}%` }} />
      </div>
      <p className="mt-1 font-mono text-[11px] text-ink-soft">
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
      className="anim-fade fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-navy/50 px-4 py-10"
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
        className={`anim-rise w-full border border-line-strong bg-cream p-6 outline-none ${wide ? "max-w-3xl" : "max-w-lg"}`}
      >
        <div className="flex items-start justify-between gap-4">
          <h2 className="font-display text-xl font-medium text-ink">{title}</h2>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="font-mono text-[18px] leading-none text-ink-faint hover:text-ink"
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
      <div className="space-y-3 text-[14px] text-ink-soft">{children}</div>
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
