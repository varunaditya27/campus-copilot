import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type { ToolActivityEntry } from "@/lib/types";
import AgentActivity from "../agent/AgentActivity";
import ChatInput from "./ChatInput";
import SuggestedPrompts from "./SuggestedPrompts";

describe("the suggested questions", () => {
  it("sends the question that was picked", async () => {
    const onSelect = vi.fn();
    render(<SuggestedPrompts onSelect={onSelect} />);
    await userEvent.click(screen.getByRole("button", { name: "Where is the library?" }));
    expect(onSelect).toHaveBeenCalledWith("Where is the library?");
  });
});

describe("the message box", () => {
  it("sends on Enter, keeps a new line on Shift+Enter, and clears after sending", async () => {
    const onSend = vi.fn();
    render(<ChatInput onSend={onSend} />);
    const box = screen.getByPlaceholderText("Ask Campus Copilot…");
    await userEvent.type(box, "first line{Shift>}{Enter}{/Shift}second");
    expect(onSend).not.toHaveBeenCalled();
    await userEvent.type(box, "{Enter}");
    expect(onSend).toHaveBeenCalledWith("first line\nsecond");
    expect(box).toHaveValue("");
  });

  it("will not send blank text", async () => {
    const onSend = vi.fn();
    render(<ChatInput onSend={onSend} />);
    await userEvent.type(screen.getByPlaceholderText("Ask Campus Copilot…"), "   {Enter}");
    expect(onSend).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Send message" })).toBeDisabled();
  });
});

describe("the compact agent activity strip", () => {
  const step = (id: string): ToolActivityEntry => ({
    id,
    tool: "get_cgpa",
    label: "Calculating your CGPA",
    status: "done",
  });

  it("is absent until the agent has done something", () => {
    const { container } = render(<AgentActivity entries={[]} compact />);
    expect(container).toBeEmptyDOMElement();
  });

  it("counts the steps", () => {
    const { rerender } = render(<AgentActivity entries={[step("a")]} compact />);
    expect(screen.getByText("Agent activity · 1 step")).toBeInTheDocument();
    rerender(<AgentActivity entries={[step("a"), step("b")]} compact />);
    expect(screen.getByText("Agent activity · 2 steps")).toBeInTheDocument();
  });
});
