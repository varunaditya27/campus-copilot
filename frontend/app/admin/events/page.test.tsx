import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "@/lib/api";
import type { CampusEvent } from "@/lib/types";
import AdminEventsPage from "./page";

const mocks = vi.hoisted(() => ({ listEvents: vi.fn(), deleteEvent: vi.fn(), auth: { role: "admin", department: null as string | null } }));
vi.mock("@/lib/api", async (importOriginal) => ({ ...(await importOriginal<typeof import("@/lib/api")>()), listEvents: mocks.listEvents }));
vi.mock("@/lib/adminApi", () => ({ deleteEvent: mocks.deleteEvent, createEvent: vi.fn(), updateEvent: vi.fn() }));
vi.mock("../../components/auth/AuthProvider", () => ({
  useAuth: () => ({
    state: { status: "signedIn", user: { role: mocks.auth.role, name: "U", faculty: mocks.auth.department ? { department: mocks.auth.department } : null } },
  }),
}));

const event = (id: string, over: Partial<CampusEvent> = {}): CampusEvent => ({
  id, name: `Event ${id}`, category: "robotics", date: "2026-12-01", time: "10:00", duration_minutes: 60, venue: "Lab", capacity: 10, registered: 4,
  organizer: "Club", description: "d", tags: [], department: null, ...over,
});

beforeEach(() => {
  mocks.listEvents.mockReset();
  mocks.deleteEvent.mockReset();
  mocks.auth.role = "admin";
  mocks.auth.department = null;
});

describe("the admin events page", () => {
  it("lets an administrator edit and delete any event", async () => {
    mocks.listEvents.mockResolvedValue([event("a"), event("b", { department: "Mechanical Engineering" })]);
    render(<AdminEventsPage />);
    await screen.findByText("Event a");
    expect(screen.getAllByRole("button", { name: /^Edit / })).toHaveLength(2);
    expect(screen.getAllByRole("button", { name: /^Delete / })).toHaveLength(2);
  });

  it("lets faculty manage only their own department's events", async () => {
    mocks.auth.role = "faculty";
    mocks.auth.department = "Information Science and Engineering";
    mocks.listEvents.mockResolvedValue([
      event("own", { department: "Information Science and Engineering" }),
      event("other", { department: "Mechanical Engineering" }),
      event("campus", { department: null }),
    ]);
    render(<AdminEventsPage />);
    await screen.findByText("Event own");
    expect(screen.getByRole("button", { name: "Edit Event own" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Edit Event other" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Edit Event campus" })).not.toBeInTheDocument();
    expect(screen.getByText("Other department")).toBeInTheDocument();
    expect(screen.getByText("Admin only")).toBeInTheDocument();
  });

  it("deletes an event nobody registered for after one confirmation", async () => {
    mocks.listEvents.mockResolvedValue([event("a", { registered: 0 })]);
    mocks.deleteEvent.mockResolvedValue({ id: "a", registrations_removed: 0 });
    render(<AdminEventsPage />);
    await userEvent.click(await screen.findByRole("button", { name: "Delete Event a" }));
    await userEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Delete event" }));
    expect(mocks.deleteEvent).toHaveBeenCalledWith("a", false);
    expect(await screen.findByText("Deleted Event a.")).toBeInTheDocument();
  });

  it("warns how many registrations would be lost and only forces the delete after a second confirmation", async () => {
    mocks.listEvents.mockResolvedValue([event("a")]);
    mocks.deleteEvent
      .mockRejectedValueOnce(new ApiError("4 students are registered. Deleting removes them.", 409, "event_has_registrations"))
      .mockResolvedValueOnce({ id: "a", registrations_removed: 4 });
    render(<AdminEventsPage />);
    await userEvent.click(await screen.findByRole("button", { name: "Delete Event a" }));
    await userEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Delete event" }));
    expect(await screen.findByText(/4 students are registered/)).toBeInTheDocument();
    expect(mocks.deleteEvent).toHaveBeenCalledTimes(1);
    await userEvent.click(screen.getByRole("button", { name: "Delete event and registrations" }));
    await waitFor(() => expect(mocks.deleteEvent).toHaveBeenLastCalledWith("a", true));
    expect(await screen.findByText(/Deleted Event a and 4 registrations/)).toBeInTheDocument();
  });

  it("shows another kind of failure inside the dialog", async () => {
    mocks.listEvents.mockResolvedValue([event("a")]);
    mocks.deleteEvent.mockRejectedValue(new ApiError("You can only manage events from your own department."));
    render(<AdminEventsPage />);
    await userEvent.click(await screen.findByRole("button", { name: "Delete Event a" }));
    await userEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Delete event" }));
    expect(await within(screen.getByRole("dialog")).findByRole("alert")).toHaveTextContent("only manage events");
  });
});
