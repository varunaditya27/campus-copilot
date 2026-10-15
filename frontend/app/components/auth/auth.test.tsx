import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { CurrentUser } from "@/lib/types";
import AuthProvider, { useAuth } from "./AuthProvider";
import RequireAuth from "./RequireAuth";
import StudentsOnly from "./StudentsOnly";

const mocks = vi.hoisted(() => ({
  getCurrentUser: vi.fn(),
  logout: vi.fn(),
  login: vi.fn(),
  registerAccount: vi.fn(),
  onSessionExpired: vi.fn(),
  replace: vi.fn(),
}));
vi.mock("@/lib/api", () => ({
  getCurrentUser: mocks.getCurrentUser,
  logout: mocks.logout,
  login: mocks.login,
  registerAccount: mocks.registerAccount,
  onSessionExpired: mocks.onSessionExpired,
}));
vi.mock("next/navigation", () => ({ useRouter: () => ({ replace: mocks.replace }), usePathname: () => "/" }));

const user = (role: CurrentUser["role"]): CurrentUser => ({
  user_id: 1, role, name: "Asha", email: "asha@example.com", student_id: role === "student" ? "1RV23IS101" : null,
  program: null, year: null, faculty: null,
});

function Who() {
  const { state } = useAuth();
  return <p>{state.status === "signedIn" ? `signed in as ${state.user.name}` : state.status}</p>;
}

beforeEach(() => Object.values(mocks).forEach((m) => m.mockReset()));

describe("the sign-in state", () => {
  it("asks the server who is signed in, because the cookies cannot be read by the page", async () => {
    mocks.getCurrentUser.mockResolvedValue(user("student"));
    render(<AuthProvider><Who /></AuthProvider>);
    expect(screen.getByText("loading")).toBeInTheDocument();
    expect(await screen.findByText("signed in as Asha")).toBeInTheDocument();
  });

  it("treats a refusal as signed out", async () => {
    mocks.getCurrentUser.mockRejectedValue(new Error("401"));
    render(<AuthProvider><Who /></AuthProvider>);
    expect(await screen.findByText("signedOut")).toBeInTheDocument();
  });

  it("signs out when the session expires and cannot be renewed", async () => {
    mocks.getCurrentUser.mockResolvedValue(user("student"));
    render(<AuthProvider><Who /></AuthProvider>);
    await screen.findByText("signed in as Asha");
    const onExpired = mocks.onSessionExpired.mock.calls[0][0] as () => void;
    act(() => onExpired());
    expect(await screen.findByText("signedOut")).toBeInTheDocument();
  });

  it("stops showing the user as signed in even when the logout request fails", async () => {
    mocks.getCurrentUser.mockResolvedValue(user("student"));
    mocks.logout.mockRejectedValue(new Error("network"));
    function Button() {
      const { logout } = useAuth();
      return <button onClick={() => logout().catch(() => {})}>out</button>;
    }
    render(<AuthProvider><Who /><Button /></AuthProvider>);
    await screen.findByText("signed in as Asha");
    await userEvent.click(screen.getByText("out"));
    expect(await screen.findByText("signedOut")).toBeInTheDocument();
  });
});

describe("the sign-in guard", () => {
  it("shows its content to a signed-in user", async () => {
    mocks.getCurrentUser.mockResolvedValue(user("student"));
    render(<AuthProvider><RequireAuth><p>secret page</p></RequireAuth></AuthProvider>);
    expect(await screen.findByText("secret page")).toBeInTheDocument();
    expect(mocks.replace).not.toHaveBeenCalled();
  });

  it("sends a signed-out visitor to the login page and shows nothing meanwhile", async () => {
    mocks.getCurrentUser.mockRejectedValue(new Error("401"));
    render(<AuthProvider><RequireAuth><p>secret page</p></RequireAuth></AuthProvider>);
    await waitFor(() => expect(mocks.replace).toHaveBeenCalledWith("/login"));
    expect(screen.queryByText("secret page")).not.toBeInTheDocument();
  });
});

describe("the students-only notice", () => {
  it("lets students through", async () => {
    mocks.getCurrentUser.mockResolvedValue(user("student"));
    render(<AuthProvider><StudentsOnly><p>chat</p></StudentsOnly></AuthProvider>);
    expect(await screen.findByText("chat")).toBeInTheDocument();
  });

  it.each([["faculty", /faculty member/], ["staff", /staff member/], ["admin", /administrator/]] as const)(
    "tells %s that the chat is for students and points to the dashboard",
    async (role, pattern) => {
      mocks.getCurrentUser.mockResolvedValue(user(role));
      render(<AuthProvider><StudentsOnly><p>chat</p></StudentsOnly></AuthProvider>);
      expect(await screen.findByText(pattern)).toBeInTheDocument();
      expect(screen.queryByText("chat")).not.toBeInTheDocument();
      expect(screen.getByRole("link", { name: /dashboard/i })).toHaveAttribute("href", "/admin");
    },
  );
});
