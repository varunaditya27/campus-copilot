"use client";

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
          The campus assistant chat is for students. Tools for managing events
          and registrations are available through the API, and a dashboard for
          them is planned.
        </p>
        <button
          type="button"
          onClick={logout}
          className="mt-5 bg-navy px-4 py-2.5 font-mono text-[12px] uppercase tracking-[0.14em] text-cream transition-colors duration-150 hover:bg-brass"
        >
          Sign out
        </button>
      </div>
    </div>
  );
}
