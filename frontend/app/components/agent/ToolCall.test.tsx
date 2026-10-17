import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import ToolCall from "./ToolCall";

const entry = { id: "c1", tool: "get_cgpa" as const, label: "Calculating your CGPA", status: "done" as const, resultSummary: "CGPA 8.45" };

describe("a tool step", () => {
  it("shows what the tool did and its result", () => {
    render(<ToolCall entry={entry} index={0} isLast />);
    expect(screen.getByText("Calculating your CGPA")).toBeInTheDocument();
    expect(screen.getByText("CGPA 8.45")).toBeInTheDocument();
  });

  it("marks a failed step differently from a finished one", () => {
    const { container: done } = render(<ToolCall entry={entry} index={0} isLast />);
    const { container: failed } = render(<ToolCall entry={{ ...entry, status: "error", resultSummary: "No student record was found." }} index={0} isLast />);
    expect(done.innerHTML).toContain("border-ink");
    expect(failed.innerHTML).toContain("border-danger");
    expect(screen.getByText("No student record was found.")).toBeInTheDocument();
  });

  it("shows a running step without a result", () => {
    const { container } = render(<ToolCall entry={{ ...entry, status: "running", resultSummary: undefined }} index={0} isLast />);
    expect(container.innerHTML).toContain("border-accent");
  });

  it("draws the connecting line for every step but the last", () => {
    const { container: middle } = render(<ToolCall entry={entry} index={0} isLast={false} />);
    const { container: last } = render(<ToolCall entry={entry} index={1} isLast />);
    expect(middle.querySelector("span[aria-hidden]")).not.toBeNull();
    expect(last.querySelector("span[aria-hidden]")).toBeNull();
  });

  it("copes with every tool the backend can report", () => {
    const tools = ["search_events", "get_fee_dues", "book_study_room", "create_grievance_ticket", "submit_event_feedback"] as const;
    for (const tool of tools) {
      const { unmount } = render(<ToolCall entry={{ ...entry, tool, label: tool }} index={0} isLast />);
      expect(screen.getByText(tool)).toBeInTheDocument();
      unmount();
    }
  });
});
