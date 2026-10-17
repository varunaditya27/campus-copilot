import Link from "next/link";

export function AuthShell({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <main className="mx-auto flex w-full max-w-md flex-1 flex-col justify-center px-6 py-12">
      <h1 className="text-head font-medium tracking-[-0.04em] text-ink">{title}</h1>
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
      <span className="text-small font-medium text-ink">{label}</span>
      <input
        {...input}
        className="mt-1.5 w-full border border-muted bg-ground px-3 py-2.5 text-body text-ink placeholder:text-muted focus:outline-2 focus:outline-offset-2 focus:outline-ink"
      />
      {hint && <span className="mt-1 block text-small text-muted">{hint}</span>}
    </label>
  );
}

export function FormError({ message }: { message: string | null }) {
  if (!message) return null;
  return (
    <p
      role="alert"
      className="bg-danger/10 px-3 py-2 text-small text-danger"
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
      className="h-12 w-full bg-accent px-4 text-body font-medium text-accent-ink transition-transform duration-150 active:scale-[0.98] disabled:opacity-60"
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
    <p className="mt-6 text-small text-ink">
      {prompt}{" "}
      <Link href={href} className="underline underline-offset-4 hover:decoration-2">
        {label}
      </Link>
    </p>
  );
}
