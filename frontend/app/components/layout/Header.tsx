"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "../auth/AuthProvider";

const NAV_LINKS = [
  { href: "/", label: "Chat" },
  { href: "/events", label: "Events" },
  { href: "/about", label: "About" },
];

export default function Header() {
  const pathname = usePathname();
  const { state, logout } = useAuth();
  const role = state.status === "signedIn" ? state.user.role : null;
  const links =
    role === "student"
      ? [...NAV_LINKS, { href: "/profile", label: "Profile" }]
      : role
        ? [...NAV_LINKS, { href: "/admin", label: "Dashboard" }]
        : NAV_LINKS;

  return (
    <header className="bg-navy text-cream">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
        <Link href="/" className="group flex items-baseline gap-3">
          <span className="font-display text-xl font-medium tracking-tight">
            Campus Copilot
          </span>
          <span className="hidden font-mono text-[11px] uppercase tracking-[0.16em] text-brass-soft sm:inline">
            Agentic Assistant
          </span>
        </Link>

        <nav className="flex items-center gap-1">
          {links.map((link) => {
            const isActive =
              link.href === "/"
                ? pathname === "/"
                : pathname.startsWith(link.href);
            return (
              <Link
                key={link.href}
                href={link.href}
                className={`relative px-3 py-2 font-mono text-xs uppercase tracking-[0.14em] transition-colors duration-150 ${
                  isActive
                    ? "text-cream"
                    : "text-cream/60 hover:text-cream"
                }`}
              >
                {link.label}
                {isActive && (
                  <span className="absolute inset-x-3 -bottom-[1px] h-[2px] bg-brass" />
                )}
              </Link>
            );
          })}
        </nav>

        <div className="flex items-center gap-3 font-mono text-xs uppercase tracking-[0.14em]">
          {state.status === "signedIn" && (
            <>
              <span className="hidden text-cream/80 sm:inline">
                {state.user.name}
              </span>
              <button
                type="button"
                onClick={logout}
                className="text-cream/60 transition-colors duration-150 hover:text-cream"
              >
                Sign out
              </button>
            </>
          )}
          {state.status === "signedOut" && pathname !== "/login" && (
            <Link
              href="/login"
              className="text-cream/60 transition-colors duration-150 hover:text-cream"
            >
              Sign in
            </Link>
          )}
        </div>
      </div>
      <div className="h-[2px] w-full bg-brass" />
      <div className="h-px w-full bg-navy-line" />
    </header>
  );
}
