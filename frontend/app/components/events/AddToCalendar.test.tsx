import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "@/lib/api";
import AddToCalendar from "./AddToCalendar";

const mocks = vi.hoisted(() => ({ downloadMyCalendar: vi.fn() }));
vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  downloadMyCalendar: mocks.downloadMyCalendar,
}));

beforeEach(() => {
  mocks.downloadMyCalendar.mockReset();
  URL.createObjectURL = vi.fn(() => "blob:calendar");
  URL.revokeObjectURL = vi.fn();
});
afterEach(() => vi.restoreAllMocks());

describe("the add to calendar button", () => {
  it("downloads the calendar file when clicked", async () => {
    const blob = new Blob(["BEGIN:VCALENDAR"], { type: "text/calendar" });
    mocks.downloadMyCalendar.mockResolvedValue(blob);
    const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
    render(<AddToCalendar />);

    await userEvent.click(screen.getByRole("button", { name: "Add my events to calendar" }));

    expect(URL.createObjectURL).toHaveBeenCalledWith(blob);
    expect(click).toHaveBeenCalledTimes(1);
    expect(URL.revokeObjectURL).toHaveBeenCalledWith("blob:calendar");
  });

  it("says so when the download fails, and can be tried again", async () => {
    mocks.downloadMyCalendar.mockRejectedValue(new ApiError("Sign in again.", 401, "unauthorized"));
    render(<AddToCalendar />);

    await userEvent.click(screen.getByRole("button", { name: "Add my events to calendar" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Sign in again.");
    expect(screen.getByRole("button", { name: "Add my events to calendar" })).toBeEnabled();
  });
});
