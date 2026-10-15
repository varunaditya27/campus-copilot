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

export default function RegisterPage() {
  const { state, register } = useAuth();
  const router = useRouter();
  const [studentId, setStudentId] = useState("");
  const [name, setName] = useState("");
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
      await register({
        student_id: studentId.trim().toUpperCase(),
        name,
        email,
        password,
      });
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "Could not create the account.",
      );
      setBusy(false);
    }
  }

  return (
    <AuthShell eyebrow="Create an account" title="Join Campus Copilot">
      <form onSubmit={handleSubmit} className="mt-8 space-y-5">
        <TextField
          label="Student ID (USN)"
          hint="For example 1RV23IS101"
          autoComplete="username"
          required
          pattern="[0-9][A-Za-z]{2}[0-9]{2}[A-Za-z]{2}[0-9]{3}"
          value={studentId}
          onChange={(e) => setStudentId(e.target.value)}
        />
        <TextField
          label="Full name"
          hint="As it appears on your student record"
          autoComplete="name"
          required
          maxLength={100}
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
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
          hint="At least 12 characters. A long phrase beats a short, complicated one."
          type="password"
          autoComplete="new-password"
          required
          minLength={12}
          maxLength={128}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
        <FormError message={error} />
        <SubmitButton busy={busy}>
          {busy ? "Creating account…" : "Create account"}
        </SubmitButton>
      </form>
      <SwitchLink prompt="Already have an account?" href="/login" label="Sign in" />
    </AuthShell>
  );
}
