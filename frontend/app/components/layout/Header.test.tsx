import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { Role } from "@/lib/types";
import Header from "./Header";

const auth = vi.hoisted(() => ({ state: { status: "signedOut" } as unknown }));
vi.mock("../auth/AuthProvider", () => ({ useAuth: () => ({ state: auth.state, logout: vi.fn() }) }));
vi.mock("next/navigation", () => ({ usePathname: () => "/events" }));

function as(role: Role | null) {
  auth.state = role ? { status: "signedIn", user: { name: "Asha", role } } : { status: "signedOut" };
  render(<Header />);
  return (name: string) => screen.queryByRole("link", { name });
}

describe("the header navigation", () => {
  it("offers the public pages and a sign-in link to a visitor", () => {
    const link = as(null);
    expect(link("Chat")).toBeInTheDocument();
    expect(link("Events")).toBeInTheDocument();
    expect(link("Sign in")).toBeInTheDocument();
    expect(link("Profile")).not.toBeInTheDocument();
    expect(link("Dashboard")).not.toBeInTheDocument();
  });

  it("offers a student their profile but no dashboard", () => {
    const link = as("student");
    expect(link("Profile")).toBeInTheDocument();
    expect(link("Dashboard")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /sign out/i })).toBeInTheDocument();
  });

  it.each(["faculty", "staff", "admin"] as const)("offers %s the dashboard and no student profile", (role) => {
    const link = as(role);
    expect(link("Dashboard")).toHaveAttribute("href", "/admin");
    expect(link("Profile")).not.toBeInTheDocument();
  });

  it("marks the current page", () => {
    as(null);
    expect(screen.getByRole("link", { name: "Events" }).className).toContain("text-cream");
    expect(screen.getByRole("link", { name: "About" }).className).toContain("text-cream/60");
  });
});
