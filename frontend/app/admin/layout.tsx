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
        <p className="max-w-md border border-line bg-cream-raised p-6 text-[14px] text-ink-soft">
          The dashboard is for faculty, staff and administrators. Students use the
          chat.
        </p>
      </div>
    );
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <nav
        aria-label="Dashboard sections"
        className="border-b border-line bg-cream-raised"
      >
        <div className="mx-auto flex max-w-6xl gap-1 overflow-x-auto px-6">
          {sections.map((section) => {
            const active = pathname.startsWith(section.href);
            return (
              <Link
                key={section.href}
                href={section.href}
                aria-current={active ? "page" : undefined}
                className={`border-b-2 px-3 py-3 font-mono text-[11px] uppercase tracking-[0.14em] transition-colors duration-150 ${
                  active
                    ? "border-brass text-ink"
                    : "border-transparent text-ink-faint hover:text-ink"
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
