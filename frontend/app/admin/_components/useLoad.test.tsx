import { act, renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ApiError } from "@/lib/api";
import { messageOf, useLoad } from "./useLoad";

describe("loading data for a page", () => {
  it("starts empty and then holds what was loaded", async () => {
    const loader = vi.fn().mockResolvedValue(["a"]);
    const { result } = renderHook(() => useLoad(loader, "fallback"));
    expect(result.current.data).toBeNull();
    await waitFor(() => expect(result.current.data).toEqual(["a"]));
    expect(result.current.error).toBeNull();
  });

  it("shows the server's message when loading fails, and a fallback for anything else", async () => {
    const { result } = renderHook(() => useLoad(() => Promise.reject(new ApiError("Not allowed", 403)), "fallback"));
    await waitFor(() => expect(result.current.error).toBe("Not allowed"));
    const other = renderHook(() => useLoad(() => Promise.reject(new Error("boom")), "Could not load it."));
    await waitFor(() => expect(other.result.current.error).toBe("Could not load it."));
  });

  it("loads again on reload, keeping the old data until the new arrives", async () => {
    let n = 0;
    const loader = vi.fn(async () => ++n);
    const { result } = renderHook(() => useLoad(loader, "x"));
    await waitFor(() => expect(result.current.data).toBe(1));
    act(() => result.current.reload());
    expect(result.current.data).toBe(1);
    await waitFor(() => expect(result.current.data).toBe(2));
  });

  it("ignores an answer that arrives after a newer request was made", async () => {
    const resolvers: Array<(v: string) => void> = [];
    let which = "first";
    const { result, rerender } = renderHook(({ id }) => useLoad(() => new Promise<string>((r) => resolvers.push(r)), id + "x"), { initialProps: { id: which } });
    which = "second";
    rerender({ id: which });
    resolvers[1]("second answer");
    await waitFor(() => expect(result.current.data).toBe("second answer"));
    resolvers[0]("stale answer");
    await new Promise((r) => setTimeout(r, 10));
    expect(result.current.data).toBe("second answer");
  });

  it("turns errors into messages", () => {
    expect(messageOf(new ApiError("Server said no"), "x")).toBe("Server said no");
    expect(messageOf("weird", "fallback")).toBe("fallback");
  });
});
