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
    </AuthShell>
  );
}
