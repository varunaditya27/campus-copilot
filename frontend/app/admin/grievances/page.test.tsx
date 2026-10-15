import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "@/lib/api";
import type { Grievance, GrievanceList } from "@/lib/adminTypes";
import GrievancesPage from "./page";

const mocks = vi.hoisted(() => ({ listGrievances: vi.fn(), updateGrievance: vi.fn() }));
vi.mock("@/lib/adminApi", () => mocks);

const ticket = (id: number, over: Partial<Grievance> = {}): Grievance => ({
  id, ticket: `GR-0000${id}`, student_id: "1RV23IS101", student_name: "Asha", program: "ISE", category: "fees",
  description: `Description ${id}`, status: "open", resolution_note: null, submitted: "2026-10-15T10:00:00Z", updated: "2026-10-15T10:00:00Z", ...over,
});

const board = (tickets: Grievance[]): GrievanceList => ({
  tickets,
  counts: { open: tickets.filter((t) => t.status === "open").length, in_progress: 0, resolved: 0 },
});

const column = (name: string) => screen.getByRole("region", { name });
const cards = (name: string) => within(column(name)).queryAllByRole("listitem").filter((li) => li.hasAttribute("draggable"));

async function open(tickets: Grievance[]) {
  mocks.listGrievances.mockResolvedValue(board(tickets));
  render(<GrievancesPage />);
  await screen.findByRole("region", { name: "Open tickets" });
}

function drag(card: HTMLElement, to: string) {
  fireEvent.dragStart(card);
  fireEvent.dragOver(column(to));
  fireEvent.drop(column(to));
}

beforeEach(() => {
  mocks.listGrievances.mockReset();
  mocks.updateGrievance.mockReset();
});

describe("the grievance board", () => {
  it("puts each ticket in the column of its status", async () => {
    await open([ticket(1), ticket(2, { status: "in_progress" }), ticket(3, { status: "resolved", resolution_note: "Done" })]);
    expect(cards("Open tickets")).toHaveLength(1);
    expect(cards("In progress tickets")).toHaveLength(1);
    expect(cards("Resolved tickets")).toHaveLength(1);
    expect(within(column("Open tickets")).getByText("Description 1")).toBeInTheDocument();
  });

  it("moves a dragged ticket at once and saves it", async () => {
    mocks.updateGrievance.mockResolvedValue(ticket(1, { status: "in_progress" }));
    await open([ticket(1)]);
    drag(cards("Open tickets")[0], "In progress tickets");
    await waitFor(() => expect(cards("In progress tickets")).toHaveLength(1));
    expect(mocks.updateGrievance).toHaveBeenCalledWith(1, "in_progress", null);
    expect(await screen.findByText(/GR-00001 is now in progress/)).toBeInTheDocument();
  });

  it("puts the ticket back and says why when the server refuses", async () => {
    mocks.updateGrievance.mockRejectedValue(new ApiError("Not allowed to do that"));
    await open([ticket(1)]);
    drag(cards("Open tickets")[0], "In progress tickets");
    expect(await screen.findByRole("alert")).toHaveTextContent("Not allowed to do that");
    await waitFor(() => expect(cards("Open tickets")).toHaveLength(1));
    expect(cards("In progress tickets")).toHaveLength(0);
  });

  it("asks for a note before resolving and refuses an empty one", async () => {
    mocks.updateGrievance.mockResolvedValue(ticket(1, { status: "resolved" }));
    await open([ticket(1)]);
    drag(cards("Open tickets")[0], "Resolved tickets");
    const dialog = await screen.findByRole("dialog");
    expect(mocks.updateGrievance).not.toHaveBeenCalled();
    await userEvent.click(within(dialog).getByRole("button", { name: "Save" }));
    expect(within(dialog).getByRole("alert")).toHaveTextContent(/resolution note/i);
    expect(mocks.updateGrievance).not.toHaveBeenCalled();
    await userEvent.type(within(dialog).getByLabelText(/resolution note/i), "Late fee reversed.");
    await userEvent.click(within(dialog).getByRole("button", { name: "Save" }));
    await waitFor(() => expect(mocks.updateGrievance).toHaveBeenCalledWith(1, "resolved", "Late fee reversed."));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  });

  it("dropping a ticket on its own column does nothing", async () => {
    await open([ticket(1)]);
    drag(cards("Open tickets")[0], "Open tickets");
    expect(mocks.updateGrievance).not.toHaveBeenCalled();
  });

  it("also moves tickets from the menu on the card, for keyboard users", async () => {
    mocks.updateGrievance.mockResolvedValue(ticket(1, { status: "in_progress" }));
    await open([ticket(1)]);
    await userEvent.selectOptions(screen.getByLabelText("Move GR-00001"), "in_progress");
    await waitFor(() => expect(mocks.updateGrievance).toHaveBeenCalledWith(1, "in_progress", null));
  });

  it("opens a ticket to read it in full", async () => {
    await open([ticket(1, { description: "A long complaint about the hostel mess." })]);
    await userEvent.click(within(column("Open tickets")).getByRole("button", { name: /A long complaint/ }));
    const dialog = await screen.findByRole("dialog", { name: /GR-00001/ });
    expect(within(dialog).getByText(/Asha \(1RV23IS101\)/)).toBeInTheDocument();
  });

  it("shows a message when the tickets cannot be loaded", async () => {
    mocks.listGrievances.mockRejectedValue(new ApiError("You do not have permission to do that."));
    render(<GrievancesPage />);
    expect(await screen.findByRole("alert")).toHaveTextContent("permission");
  });
});
