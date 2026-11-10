import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import InstallPrompt from "./InstallPrompt";

function setup({ installed = false, userAgent = "Mozilla/5.0 (X11; Linux x86_64) Chrome/120" } = {}) {
  window.matchMedia = vi.fn().mockReturnValue({ matches: installed }) as unknown as typeof window.matchMedia;
  vi.spyOn(navigator, "userAgent", "get").mockReturnValue(userAgent);
}

beforeEach(() => setup());
afterEach(() => vi.restoreAllMocks());

describe("the install prompt", () => {
  it("shows nothing when there is nothing to offer", () => {
    render(<InstallPrompt />);
    expect(screen.queryByRole("heading")).not.toBeInTheDocument();
  });

  it("shows nothing once the app is installed", () => {
    setup({ installed: true });
    render(<InstallPrompt />);
    act(() => {
      window.dispatchEvent(new Event("beforeinstallprompt"));
    });
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  it("offers an install button when the browser says the app can be installed, and asks it to install", async () => {
    render(<InstallPrompt />);
    const offer = Object.assign(new Event("beforeinstallprompt", { cancelable: true }), {
      prompt: vi.fn().mockResolvedValue(undefined),
    });
    act(() => {
      window.dispatchEvent(offer);
    });
    expect(offer.defaultPrevented).toBe(true);

    await userEvent.click(await screen.findByRole("button", { name: "Install the app" }));

    expect(offer.prompt).toHaveBeenCalledTimes(1);
  });

  it("tells iPhone and iPad users how to add it to the home screen, since they get no install button", () => {
    setup({ userAgent: "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) Safari/604.1" });
    render(<InstallPrompt />);
    expect(screen.getByText(/Add to Home Screen/)).toBeInTheDocument();
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });
});
