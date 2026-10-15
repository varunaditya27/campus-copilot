import Link from "next/link";

export function AuthShell({
  eyebrow,
  title,
  children,
}: {
  eyebrow: string;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <main className="mx-auto flex w-full max-w-md flex-1 flex-col justify-center px-6 py-12">
      <p className="font-mono text-[11px] uppercase tracking-[0.16em] text-brass">
        {eyebrow}
      </p>
      <h1 className="mt-2 font-display text-3xl font-medium tracking-tight text-ink">
        {title}
      </h1>
      {children}
    </main>
  );
}

export function TextField({
  label,
  hint,
  ...input
}: {
  label: string;
  hint?: string;
} & React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <label className="block">
      <span className="font-mono text-[11px] uppercase tracking-[0.14em] text-ink-faint">
        {label}
      </span>
      <input
        {...input}
        className="mt-1.5 w-full border border-line-strong bg-cream-raised px-3 py-2.5 text-[15px] text-ink placeholder:text-ink-faint focus:border-brass focus:outline-none"
      />
      {hint && <span className="mt-1 block text-[12px] text-ink-faint">{hint}</span>}
    </label>
  );
}

export function FormError({ message }: { message: string | null }) {
  if (!message) return null;
  return (
    <p
      role="alert"
      className="border border-rust/40 bg-rust/5 px-3 py-2 text-[13px] text-rust"
    >
      {message}
    </p>
  );
}

export function SubmitButton({
  busy,
  children,
}: {
  busy: boolean;
  children: React.ReactNode;
}) {
  return (
    <button
      type="submit"
      disabled={busy}
      className="w-full bg-navy px-4 py-3 font-mono text-[12px] uppercase tracking-[0.14em] text-cream transition-colors duration-150 hover:bg-brass disabled:opacity-60"
    >
      {children}
    </button>
  );
}

export function SwitchLink({
  prompt,
  href,
  label,
}: {
  prompt: string;
  href: string;
  label: string;
}) {
  return (
    <p className="mt-6 text-[13.5px] text-ink-soft">
      {prompt}{" "}
      <Link href={href} className="text-navy underline decoration-brass underline-offset-4 hover:text-brass">
        {label}
      </Link>
    </p>
  );
}
