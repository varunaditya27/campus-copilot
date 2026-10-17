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
      <div className="max-w-md bg-surface p-6">
        <h1 className="text-lead font-medium text-ink">
          You are signed in as {LABELS[state.user.role]}
        </h1>
        <p className="mt-3 text-body text-ink">
          The campus assistant chat is for students. Managing events, students,
          grievances and the knowledge base is done in the dashboard.
        </p>
        <div className="mt-5 flex items-center gap-5">
          <Link
            href="/admin"
            className="bg-accent px-4 py-2.5 text-small font-medium text-accent-ink transition-transform duration-150 active:scale-[0.98]"
          >
            Open the dashboard
          </Link>
          <button
            type="button"
            onClick={logout}
            className="text-small font-medium text-ink underline underline-offset-4 hover:decoration-2"
          >
            Sign out
          </button>
        </div>
      </div>
    </div>
  );
}
