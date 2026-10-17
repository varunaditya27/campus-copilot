import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { Banner, ConfirmDialog, Gauge, Modal, formatDateTime } from "./ui";

describe("the capacity gauge", () => {
  it("is a labelled meter showing how full something is", () => {
    render(<Gauge value={33} max={50} label="Seats taken" />);
    const meter = screen.getByRole("meter", { name: "Seats taken" });
    expect(meter).toHaveAttribute("aria-valuenow", "33");
    expect(meter).toHaveAttribute("aria-valuemax", "50");
    expect(screen.getByText("33 / 50 (66%)")).toBeInTheDocument();
  });

  it("turns warning and full colours as it fills", () => {
    const colour = (value: number) => {
      const { container, unmount } = render(<Gauge value={value} max={10} label="x" />);
      const bar = container.querySelector("[role=meter] > div")!.className;
      unmount();
      return bar;
    };
    expect(colour(5)).toContain("bg-muted");
    expect(colour(8)).toContain("bg-ink");
    expect(colour(10)).toContain("bg-danger");
  });

  it("never overflows and copes with a zero maximum", () => {
    const { container } = render(<Gauge value={12} max={10} label="x" />);
    expect((container.querySelector("[role=meter] > div") as HTMLElement).style.width).toBe("100%");
    render(<Gauge value={0} max={0} label="y" />);
    expect(screen.getByText("0 / 0 (0%)")).toBeInTheDocument();
  });
});

describe("the dialog", () => {
  it("is a modal dialog with a title and takes focus", () => {
    render(<Modal title="Edit event" onClose={() => {}}><p>content</p></Modal>);
    const dialog = screen.getByRole("dialog", { name: "Edit event" });
    expect(dialog).toHaveAttribute("aria-modal", "true");
    expect(dialog).toHaveFocus();
  });

  it("closes on Escape, on the close button and on a click outside, but not on a click inside", async () => {
    const onClose = vi.fn();
    render(<Modal title="T" onClose={onClose}><p>content</p></Modal>);
    await userEvent.click(screen.getByText("content"));
    expect(onClose).not.toHaveBeenCalled();
    await userEvent.keyboard("{Escape}");
    expect(onClose).toHaveBeenCalledTimes(1);
    await userEvent.click(screen.getByRole("button", { name: "Close" }));
    expect(onClose).toHaveBeenCalledTimes(2);
    await userEvent.click(screen.getByRole("dialog").parentElement!);
    expect(onClose).toHaveBeenCalledTimes(3);
  });

  it("gives focus back to what opened it", () => {
    render(<button>open</button>);
    const opener = screen.getByText("open");
    opener.focus();
    const { unmount } = render(<Modal title="T" onClose={() => {}}><p>x</p></Modal>);
    expect(opener).not.toHaveFocus();
    unmount();
    expect(opener).toHaveFocus();
  });
});

describe("the confirmation dialog", () => {
  it("runs the action on confirm and closes on cancel", async () => {
    const onConfirm = vi.fn();
    const onCancel = vi.fn();
    render(<ConfirmDialog title="Delete it?" confirmLabel="Delete" busy={false} error={null} onConfirm={onConfirm} onCancel={onCancel}><p>This cannot be undone.</p></ConfirmDialog>);
    expect(screen.getByText("This cannot be undone.")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Delete" }));
    expect(onConfirm).toHaveBeenCalledTimes(1);
    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(onCancel).toHaveBeenCalledTimes(1);
  });

  it("disables both buttons while working and shows an error as an alert", () => {
    render(<ConfirmDialog title="T" confirmLabel="Delete" busy error="Could not delete" onConfirm={() => {}} onCancel={() => {}}><p>x</p></ConfirmDialog>);
    expect(screen.getByRole("button", { name: "Working…" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Cancel" })).toBeDisabled();
    expect(screen.getByRole("alert")).toHaveTextContent("Could not delete");
  });
});

describe("small helpers", () => {
  it("announces errors as alerts and other notices politely", () => {
    render(<><Banner kind="error">bad</Banner><Banner kind="success">good</Banner></>);
    expect(screen.getByRole("alert")).toHaveTextContent("bad");
    expect(screen.getByRole("status")).toHaveTextContent("good");
  });

  it("formats a date and passes through what it cannot read", () => {
    expect(formatDateTime("2026-10-15T12:00:00Z")).toMatch(/2026/);
    expect(formatDateTime("not a date")).toBe("not a date");
  });
});
