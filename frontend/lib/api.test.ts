import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError, getCurrentUser, listEvents, onSessionExpired, post, toApiError } from "./api";

function reply(status: number, body: unknown = {}): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

let fetchMock: ReturnType<typeof vi.fn>;

beforeEach(() => {
  fetchMock = vi.fn();
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  onSessionExpired(null);
  vi.unstubAllGlobals();
});

describe("reading an error from the server", () => {
  it("uses the server's message and error code", async () => {
    const error = await toApiError("/x", reply(409, { error_code: "event_has_registrations", message: "2 students are registered." }));
    expect(error).toBeInstanceOf(ApiError);
    expect([error.message, error.status, error.code]).toEqual(["2 students are registered.", 409, "event_has_registrations"]);
  });

  it("falls back to a plain message when the body is not JSON", async () => {
    const error = await toApiError("/x", new Response("<html>oops</html>", { status: 502 }));
    expect(error.message).toBe("Request to /x failed (502)");
    expect(error.code).toBeUndefined();
  });
});

describe("calls to the backend", () => {
  it("sends the session cookies and parses the JSON answer", async () => {
    fetchMock.mockResolvedValueOnce(reply(200, [{ id: "evt_1" }]));
    expect(await listEvents()).toEqual([{ id: "evt_1" }]);
    expect(fetchMock.mock.calls[0][1]).toMatchObject({ credentials: "include" });
  });

  it("turns a failed response into an ApiError with the server's message", async () => {
    fetchMock.mockResolvedValueOnce(reply(404, { error_code: "not_found", message: "No such event" }));
    await expect(listEvents()).rejects.toMatchObject({ message: "No such event", status: 404, code: "not_found" });
  });

  it("reports an unreachable server in plain words", async () => {
    fetchMock.mockRejectedValueOnce(new TypeError("Failed to fetch"));
    await expect(listEvents()).rejects.toThrow(/reach/i);
  });

  it("sends a JSON body with the right header", async () => {
    fetchMock.mockResolvedValueOnce(reply(200, {}));
    await post("/api/things", { a: 1 });
    const init = fetchMock.mock.calls[0][1];
    expect(init.method).toBe("POST");
    expect(init.body).toBe('{"a":1}');
    expect(init.headers).toMatchObject({ "Content-Type": "application/json" });
  });
});

describe("an expired session", () => {
  it("is renewed once and the call retried", async () => {
    fetchMock
      .mockResolvedValueOnce(reply(401))
      .mockResolvedValueOnce(reply(200)) // the refresh
      .mockResolvedValueOnce(reply(200, { name: "Asha" }));
    expect(await getCurrentUser()).toEqual({ name: "Asha" });
    expect(fetchMock.mock.calls.map((c) => String(c[0]).split("/api/")[1])).toEqual(["auth/me", "auth/refresh", "auth/me"]);
  });

  it("tells the app the session ended when it cannot be renewed", async () => {
    const expired = vi.fn();
    onSessionExpired(expired);
    fetchMock.mockResolvedValueOnce(reply(401)).mockResolvedValueOnce(reply(401, { message: "Sign in again" }));
    await expect(getCurrentUser()).rejects.toBeInstanceOf(ApiError);
    expect(expired).toHaveBeenCalledTimes(1);
  });

  it("does not try to renew the session during sign-in itself", async () => {
    fetchMock.mockResolvedValueOnce(reply(401, { message: "Wrong email or password" }));
    await expect(post("/api/auth/login", {})).rejects.toMatchObject({ message: "Wrong email or password" });
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("shares one renewal between simultaneous calls", async () => {
    let refreshes = 0;
    fetchMock.mockImplementation(async (url: string) => {
      if (String(url).endsWith("/api/auth/refresh")) {
        refreshes += 1;
        return reply(200);
      }
      return refreshes === 0 ? reply(401) : reply(200, []);
    });
    await Promise.all([listEvents(), listEvents(), listEvents()]);
    expect(refreshes).toBe(1);
  });
});
