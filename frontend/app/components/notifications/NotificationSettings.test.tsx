import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "@/lib/api";
import NotificationSettings from "./NotificationSettings";

const mocks = vi.hoisted(() => ({
  getPushPublicKey: vi.fn(),
  savePushSubscription: vi.fn(),
  deletePushSubscription: vi.fn(),
}));
vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  ...mocks,
}));

const ENDPOINT = "https://fcm.googleapis.com/fcm/send/abc";
const subscription = () => ({
  endpoint: ENDPOINT,
  toJSON: () => ({ endpoint: ENDPOINT, keys: { p256dh: "k", auth: "a" } }),
  unsubscribe: vi.fn().mockResolvedValue(true),
});

let existing: ReturnType<typeof subscription> | null;
const pushManager = { getSubscription: vi.fn(), subscribe: vi.fn() };

function browserCan(permission: NotificationPermission = "default") {
  const registration = { pushManager };
  Object.defineProperty(navigator, "serviceWorker", {
    configurable: true,
    value: { getRegistration: vi.fn().mockResolvedValue(registration), ready: Promise.resolve(registration) },
  });
  vi.stubGlobal("PushManager", class {});
  vi.stubGlobal("Notification", { permission, requestPermission: vi.fn().mockResolvedValue("granted") });
}

beforeEach(() => {
  Object.values(mocks).forEach((m) => m.mockReset());
  pushManager.getSubscription.mockReset();
  pushManager.subscribe.mockReset();
  existing = null;
  pushManager.getSubscription.mockImplementation(async () => existing);
  mocks.getPushPublicKey.mockResolvedValue({ public_key: "AAEC" });
  mocks.savePushSubscription.mockResolvedValue(undefined);
  mocks.deletePushSubscription.mockResolvedValue(undefined);
});
afterEach(() => {
  vi.unstubAllGlobals();
  Reflect.deleteProperty(navigator, "serviceWorker");
});

describe("the notification settings", () => {
  it("says so when the browser cannot show notifications", async () => {
    render(<NotificationSettings />);
    expect(await screen.findByText(/can.t show notifications/i)).toBeInTheDocument();
  });

  it("says so when the server has push switched off", async () => {
    browserCan();
    mocks.getPushPublicKey.mockRejectedValue(new ApiError("off", 404, "push_unavailable"));
    render(<NotificationSettings />);
    expect(await screen.findByText(/not set up on this server/i)).toBeInTheDocument();
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  it("says so when notifications are blocked in the browser", async () => {
    browserCan("denied");
    render(<NotificationSettings />);
    expect(await screen.findByText(/blocked in your browser/i)).toBeInTheDocument();
  });

  it("turns notifications on: asks permission, subscribes with the server's key and tells the server", async () => {
    browserCan();
    const created = subscription();
    pushManager.subscribe.mockResolvedValue(created);
    render(<NotificationSettings />);

    await userEvent.click(await screen.findByRole("button", { name: "Turn on notifications" }));

    expect(await screen.findByRole("button", { name: "Turn off notifications" })).toBeInTheDocument();
    expect(Notification.requestPermission).toHaveBeenCalled();
    expect(pushManager.subscribe).toHaveBeenCalledWith({
      userVisibleOnly: true,
      applicationServerKey: new Uint8Array([0, 1, 2]),
    });
    expect(mocks.savePushSubscription).toHaveBeenCalledWith(created.toJSON());
  });

  it("stays off when the student refuses the permission", async () => {
    browserCan();
    vi.mocked(Notification.requestPermission).mockResolvedValue("denied");
    render(<NotificationSettings />);

    await userEvent.click(await screen.findByRole("button", { name: "Turn on notifications" }));

    expect(await screen.findByText(/blocked in your browser/i)).toBeInTheDocument();
    expect(pushManager.subscribe).not.toHaveBeenCalled();
    expect(mocks.savePushSubscription).not.toHaveBeenCalled();
  });

  it("shows a browser that is already subscribed as on, and makes sure the server has it for this student", async () => {
    browserCan("granted");
    existing = subscription();
    render(<NotificationSettings />);

    expect(await screen.findByRole("button", { name: "Turn off notifications" })).toBeInTheDocument();
    await waitFor(() => expect(mocks.savePushSubscription).toHaveBeenCalledWith(existing!.toJSON()));
  });

  it("turns notifications off in the browser and on the server", async () => {
    browserCan("granted");
    existing = subscription();
    render(<NotificationSettings />);

    await userEvent.click(await screen.findByRole("button", { name: "Turn off notifications" }));

    expect(await screen.findByRole("button", { name: "Turn on notifications" })).toBeInTheDocument();
    expect(mocks.deletePushSubscription).toHaveBeenCalledWith(ENDPOINT);
    expect(existing.unsubscribe).toHaveBeenCalled();
  });

  it("explains a failure and can be tried again", async () => {
    browserCan();
    pushManager.subscribe.mockRejectedValue(new Error("push service unreachable"));
    render(<NotificationSettings />);

    await userEvent.click(await screen.findByRole("button", { name: "Turn on notifications" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/could not turn on notifications/i);
    expect(screen.getByRole("button", { name: "Turn on notifications" })).toBeEnabled();
  });
});
