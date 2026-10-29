"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ApiError } from "@/lib/api";
import { useAuth } from "../components/auth/AuthProvider";
import {
  AuthShell,
  FormError,
  SubmitButton,
  SwitchLink,
  TextField,
} from "../components/auth/AuthForm";

export default function LoginPage() {
  const { state, login } = useAuth();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (state.status === "signedIn") {
      router.replace("/");
    }
  }, [state.status, router]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await login({ email, password });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not sign in.");
      setBusy(false);
    }
  }

  return (
    <AuthShell title="Sign in">
      <form onSubmit={handleSubmit} className="mt-8 space-y-5">
        <TextField
          label="Email"
          type="email"
          autoComplete="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
        <TextField
          label="Password"
          type="password"
          autoComplete="current-password"
          required
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
        <FormError message={error} />
        <SubmitButton busy={busy}>{busy ? "Signing in…" : "Sign in"}</SubmitButton>
      </form>
      <SwitchLink prompt="New here?" href="/register" label="Create an account" />
      <DemoAccounts
        onPick={(account) => {
          setEmail(account.email);
          setPassword(account.password);
        }}
      />
    </AuthShell>
  );
}

// Fills the form with a local demo account. Shown only when frontend/.env.local holds the
// credentials; each variable is named in full because Next.js inlines only literal names.
function DemoAccounts({ onPick }: { onPick: (account: { email: string; password: string }) => void }) {
  const accounts = [
    {
      label: "Fill in demo student",
      email: process.env.NEXT_PUBLIC_DEMO_STUDENT_EMAIL,
      password: process.env.NEXT_PUBLIC_DEMO_STUDENT_PASSWORD,
    },
    {
      label: "Fill in demo admin",
      email: process.env.NEXT_PUBLIC_DEMO_ADMIN_EMAIL,
      password: process.env.NEXT_PUBLIC_DEMO_ADMIN_PASSWORD,
    },
  ].filter((a): a is { label: string; email: string; password: string } => Boolean(a.email && a.password));
  if (accounts.length === 0) return null;

  return (
    <div className="mt-8 flex flex-wrap gap-2">
      {accounts.map((a) => (
        <button
          key={a.label}
          type="button"
          onClick={() => onPick(a)}
          className="min-h-10 bg-ink/10 px-4 py-2 text-small font-medium text-ink transition duration-150 hover:bg-ink hover:text-ground focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink active:scale-[0.98]"
        >
          {a.label}
        </button>
      ))}
    </div>
  );
}
