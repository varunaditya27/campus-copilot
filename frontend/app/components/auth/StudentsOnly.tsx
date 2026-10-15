"use client";

import Link from "next/link";
import { useAuth } from "./AuthProvider";

const LABELS = {
  faculty: "a faculty member",
  staff: "a staff member",
  admin: "an administrator",
} as const;

// The chat is for students. Other roles are told so, instead of meeting 403 errors.
export default function StudentsOnly({
  children,
}: {
  children: React.ReactNode;
}) {
  const { state, logout } = useAuth();

  if (state.status !== "signedIn" || state.user.role === "student") {
    return <>{children}</>;
  }

  return (
    <div className="flex flex-1 items-center justify-center px-6">
      <div className="max-w-md border border-line bg-cream-raised p-6">
        <p className="font-mono text-[11px] uppercase tracking-[0.16em] text-brass">
          {state.user.role}
        </p>
        <h1 className="mt-2 font-display text-2xl font-medium tracking-tight text-ink">
          You are signed in as {LABELS[state.user.role]}
        </h1>
        <p className="mt-3 text-[14px] leading-relaxed text-ink-soft">
          The campus assistant chat is for students. Managing events, students,
          grievances and the knowledge base is done in the dashboard.
        </p>
        <div className="mt-5 flex gap-3">
          <Link
            href="/admin"
            className="bg-navy px-4 py-2.5 font-mono text-[12px] uppercase tracking-[0.14em] text-cream transition-colors duration-150 hover:bg-brass"
          >
            Open the dashboard
          </Link>
          <button
            type="button"
            onClick={logout}
            className="border border-line-strong px-4 py-2.5 font-mono text-[12px] uppercase tracking-[0.14em] text-ink transition-colors duration-150 hover:border-brass"
          >
            Sign out
          </button>
        </div>
      </div>
    </div>
  );
}
