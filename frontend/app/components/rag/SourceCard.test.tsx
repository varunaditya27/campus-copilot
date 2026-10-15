import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import SourceCard from "./SourceCard";

describe("a source card", () => {
  it("shows the document and section, and reveals the passage on click", async () => {
    render(<SourceCard source={{ document: "library.md", section: "Hours", snippet: "Opens at eight." }} />);
    expect(screen.getByText("library.md")).toBeInTheDocument();
    expect(screen.getByText(/Hours/)).toBeInTheDocument();
    expect(screen.queryByText("Opens at eight.")).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button"));
    expect(screen.getByText("Opens at eight.")).toBeInTheDocument();
    expect(screen.getByRole("button")).toHaveAttribute("aria-expanded", "true");
    await userEvent.click(screen.getByRole("button"));
    expect(screen.queryByText("Opens at eight.")).not.toBeInTheDocument();
  });

  it("does not expand when there is no passage to show", async () => {
    render(<SourceCard source={{ document: "hostel.md" }} />);
    await userEvent.click(screen.getByRole("button"));
    expect(screen.getByRole("button")).toHaveAttribute("aria-expanded", "false");
  });
});
