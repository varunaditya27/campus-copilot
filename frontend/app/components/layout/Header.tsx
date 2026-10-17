"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "../auth/AuthProvider";

const NAV_LINKS = [
  { href: "/", label: "Chat" },
  { href: "/events", label: "Events" },
];

export default function Header() {
  const pathname = usePathname();
  const { state, logout } = useAuth();
  const [menuOpen, setMenuOpen] = useState(false);
  const role = state.status === "signedIn" ? state.user.role : null;
  const links =
    role === "student"
      ? [...NAV_LINKS, { href: "/profile", label: "Profile" }]
      : role
        ? [...NAV_LINKS, { href: "/admin", label: "Dashboard" }]
        : NAV_LINKS;

  return (
    <header className="sticky top-0 z-30 h-[var(--header-h)] bg-ground text-ink">
      <div className="flex h-full items-center gap-6 px-5 md:px-6">
        <Link href="/" className="mr-auto text-xl font-medium tracking-[-0.03em]">
          Campus Copilot
        </Link>

        <button
          type="button"
          onClick={() => setMenuOpen((v) => !v)}
          aria-expanded={menuOpen}
          aria-controls="site-nav"
          className="text-[15px] underline-offset-[6px] hover:underline md:hidden"
        >
          Menu
        </button>

        <nav
          id="site-nav"
          className={`${menuOpen ? "flex" : "hidden"} absolute inset-x-0 top-[var(--header-h)] flex-col gap-1 bg-surface px-5 py-4 text-ink md:static md:flex md:flex-row md:gap-6 md:bg-transparent md:p-0 md:text-inherit`}
        >
          {links.map((link) => {
            const isActive =
              link.href === "/" ? pathname === "/" : pathname.startsWith(link.href);
            return (
              <Link
                key={link.href}
                href={link.href}
                onClick={() => setMenuOpen(false)}
                aria-current={isActive ? "page" : undefined}
                className={`py-2 text-[15px] decoration-2 underline-offset-[6px] md:py-0 ${
                  isActive ? "underline" : "hover:underline"
                }`}
              >
                {link.label}
              </Link>
            );
          })}
        </nav>

        {state.status === "signedIn" && (
          <div className="flex items-center gap-4 text-[15px]">
            <span className="hidden lg:inline">{state.user.name}</span>
            <button
              type="button"
              onClick={logout}
              className="underline-offset-[6px] hover:underline"
            >
              Sign out
            </button>
          </div>
        )}
        {state.status === "signedOut" && pathname !== "/login" && (
          <Link
            href="/login"
            className="bg-ink px-4 py-2.5 text-[15px] font-medium text-ground transition-transform duration-150 active:scale-[0.97]"
          >
            Sign in
          </Link>
        )}
      </div>
    </header>
  );
}
