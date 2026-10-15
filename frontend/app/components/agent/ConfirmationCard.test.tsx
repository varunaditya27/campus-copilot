import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "@/lib/api";
import type { Confirmation } from "@/lib/types";
import ConfirmationCard from "./ConfirmationCard";

const mocks = vi.hoisted(() => ({ confirmAction: vi.fn(), cancelAction: vi.fn() }));
vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  confirmAction: mocks.confirmAction,
  cancelAction: mocks.cancelAction,
}));

const confirmation: Confirmation = {
  action_id: "a-1",
  action: "register_for_event",
  title: "Register for AI Workshop",
  lines: [
    { label: "Event", value: "AI Workshop" },
    { label: "When", value: "2026-09-01 at 10:00" },
  ],
  expires_at: "2026-09-01T10:00:00Z",
};

const outcome = (over = {}) => ({ action_id: "a-1", status: "confirmed", success: true, message: "You're registered for AI Workshop.", details: { "Registration ID": "REG-00001" }, ...over });

beforeEach(() => {
  mocks.confirmAction.mockReset();
  mocks.cancelAction.mockReset();
});

describe("the confirmation card", () => {
  it("shows what is about to happen and does nothing until asked", () => {
    render(<ConfirmationCard confirmation={confirmation} />);
    expect(screen.getByText("Register for AI Workshop")).toBeInTheDocument();
    expect(screen.getByText("2026-09-01 at 10:00")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Confirm" })).toBeEnabled();
    expect(mocks.confirmAction).not.toHaveBeenCalled();
  });

  it("sends only the action id when confirmed, then shows the result and its details", async () => {
    mocks.confirmAction.mockResolvedValue(outcome());
    render(<ConfirmationCard confirmation={confirmation} />);
    await userEvent.click(screen.getByRole("button", { name: "Confirm" }));
    expect(mocks.confirmAction).toHaveBeenCalledWith("a-1");
    expect(await screen.findByText("You're registered for AI Workshop.")).toBeInTheDocument();
    expect(screen.getByText(/REG-00001/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Confirm" })).not.toBeInTheDocument();
  });

  it("explains a refusal in the server's own words", async () => {
    mocks.confirmAction.mockResolvedValue(outcome({ status: "failed", success: false, message: "This event is full", details: {} }));
    render(<ConfirmationCard confirmation={confirmation} />);
    await userEvent.click(screen.getByRole("button", { name: "Confirm" }));
    expect(await screen.findByText("This event is full")).toBeInTheDocument();
    expect(screen.getByText(/not done/i)).toBeInTheDocument();
  });

  it("cancels without doing anything", async () => {
    mocks.cancelAction.mockResolvedValue(outcome({ status: "cancelled", success: false, message: "Cancelled. Nothing was done.", details: {} }));
    render(<ConfirmationCard confirmation={confirmation} />);
    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(mocks.cancelAction).toHaveBeenCalledWith("a-1");
    expect(mocks.confirmAction).not.toHaveBeenCalled();
    expect(await screen.findByText(/Cancelled. Nothing was done./)).toBeInTheDocument();
  });

  it("says when the time to approve has run out", async () => {
    mocks.confirmAction.mockRejectedValue(new ApiError("expired", 410, "action_expired"));
    render(<ConfirmationCard confirmation={confirmation} />);
    await userEvent.click(screen.getByRole("button", { name: "Confirm" }));
    expect(await screen.findByText(/took too long to approve/i)).toBeInTheDocument();
  });

  it("keeps the buttons usable after a network failure and shows why", async () => {
    mocks.confirmAction.mockRejectedValue(new ApiError("The server could not be reached."));
    render(<ConfirmationCard confirmation={confirmation} />);
    await userEvent.click(screen.getByRole("button", { name: "Confirm" }));
    expect(await screen.findByText("The server could not be reached.")).toBeInTheDocument();
    await waitFor(() => expect(screen.getByRole("button", { name: "Confirm" })).toBeEnabled());
  });

  it("cannot be confirmed twice while the first request is still running", async () => {
    let finish: (value: unknown) => void = () => {};
    mocks.confirmAction.mockReturnValue(new Promise((resolve) => (finish = resolve)));
    render(<ConfirmationCard confirmation={confirmation} />);
    await userEvent.click(screen.getByRole("button", { name: "Confirm" }));
    expect(screen.getByRole("button", { name: /working/i })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Cancel" })).toBeDisabled();
    finish(outcome());
    await screen.findByText("You're registered for AI Workshop.");
    expect(mocks.confirmAction).toHaveBeenCalledTimes(1);
  });
});
