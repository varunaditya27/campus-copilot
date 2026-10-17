"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { sectionsFor } from "@/lib/adminSections";
import RequireAuth from "../components/auth/RequireAuth";
import { useAuth } from "../components/auth/AuthProvider";

function Dashboard({ children }: { children: React.ReactNode }) {
  const { state } = useAuth();
  const pathname = usePathname();
  if (state.status !== "signedIn") return null;

  const sections = sectionsFor(state.user.role);
  if (sections.length === 0) {
    return (
      <div className="flex flex-1 items-center justify-center px-6">
        <p className="max-w-md bg-surface p-6 text-body text-ink">
          The dashboard is for faculty, staff and administrators. Students use the
          chat.
        </p>
      </div>
    );
  }

  return (
    <div className="flex h-[calc(100dvh-var(--header-h))] flex-col">
      <nav
        aria-label="Dashboard sections"
        className="bg-surface"
      >
        <div className="mx-auto flex max-w-6xl gap-1 overflow-x-auto px-6">
          {sections.map((section) => {
            const active = pathname.startsWith(section.href);
            return (
              <Link
                key={section.href}
                href={section.href}
                aria-current={active ? "page" : undefined}
                className={`border-b-2 px-3 py-3 text-small font-medium transition-colors duration-150 ${
                  active
                    ? "border-ink text-ink"
                    : "border-transparent text-muted hover:text-ink"
                }`}
              >
                {section.label}
              </Link>
            );
          })}
        </div>
      </nav>
      <div className="thin-scroll min-h-0 flex-1 overflow-y-auto">
        <div className="mx-auto w-full max-w-6xl px-6 py-8">{children}</div>
      </div>
    </div>
  );
}

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  return (
    <RequireAuth>
      <Dashboard>{children}</Dashboard>
    </RequireAuth>
  );
}
