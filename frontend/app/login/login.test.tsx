import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import LoginPage from "./page";

vi.mock("../components/auth/AuthProvider", () => ({
  useAuth: () => ({ state: { status: "signedOut" }, login: vi.fn() }),
}));
vi.mock("next/navigation", () => ({ useRouter: () => ({ replace: vi.fn() }) }));

afterEach(() => vi.unstubAllEnvs());

describe("the demo account buttons", () => {
  it("fill the sign-in form with the configured account", async () => {
    vi.stubEnv("NEXT_PUBLIC_DEMO_STUDENT_EMAIL", "student@example.com");
    vi.stubEnv("NEXT_PUBLIC_DEMO_STUDENT_PASSWORD", "student-password");
    vi.stubEnv("NEXT_PUBLIC_DEMO_ADMIN_EMAIL", "admin@example.com");
    vi.stubEnv("NEXT_PUBLIC_DEMO_ADMIN_PASSWORD", "admin-password");
    render(<LoginPage />);

    await userEvent.click(screen.getByRole("button", { name: "Fill in demo admin" }));
    expect(screen.getByLabelText("Email")).toHaveValue("admin@example.com");
    expect(screen.getByLabelText("Password")).toHaveValue("admin-password");

    await userEvent.click(screen.getByRole("button", { name: "Fill in demo student" }));
    expect(screen.getByLabelText("Email")).toHaveValue("student@example.com");
  });

  it("are absent when no demo accounts are configured", () => {
    vi.stubEnv("NEXT_PUBLIC_DEMO_STUDENT_EMAIL", "");
    vi.stubEnv("NEXT_PUBLIC_DEMO_ADMIN_EMAIL", "");
    render(<LoginPage />);
    expect(screen.queryByRole("button", { name: /demo/ })).not.toBeInTheDocument();
  });
});
