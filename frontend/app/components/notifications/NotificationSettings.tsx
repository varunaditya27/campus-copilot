"use client";

import { useEffect, useState } from "react";
import {
  ApiError,
  deletePushSubscription,
  getPushPublicKey,
  savePushSubscription,
} from "@/lib/api";
import { currentPushSubscription, urlBase64ToUint8Array } from "@/lib/push";

type Status = "checking" | "unsupported" | "unavailable" | "blocked" | "off" | "on";

async function findStatus(): Promise<Status> {
  if (!("serviceWorker" in navigator) || !("PushManager" in window) || !("Notification" in window)) {
    return "unsupported";
  }
  // The service worker only exists in the built app, not in development.
  if (!(await navigator.serviceWorker.getRegistration())) return "unsupported";
  try {
    await getPushPublicKey();
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) return "unavailable";
  }
  if (Notification.permission === "denied") return "blocked";
  const subscription = await currentPushSubscription();
  if (!subscription) return "off";
  // This browser may have been subscribed by someone else who used it: make it this student's.
  await savePushSubscription(subscription.toJSON()).catch(() => {});
  return "on";
}

const NOTES: Partial<Record<Status, string>> = {
  unsupported: "This browser can’t show notifications.",
  unavailable: "Notifications are not set up on this server.",
  blocked: "Notifications are blocked in your browser settings. Allow them for this site to turn them on.",
};

// Lets a student choose whether this browser gets a message when a registration is confirmed or a seat opens up.
export default function NotificationSettings() {
  const [status, setStatus] = useState<Status>("checking");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    findStatus().then(
      (found) => active && setStatus(found),
      () => active && setStatus("unsupported"),
    );
    return () => {
      active = false;
    };
  }, []);

  async function enable() {
    setBusy(true);
    setError(null);
    try {
      const permission = await Notification.requestPermission();
      if (permission !== "granted") {
        setStatus(permission === "denied" ? "blocked" : "off");
        return;
      }
      const { public_key } = await getPushPublicKey();
      const registration = await navigator.serviceWorker.ready;
      const subscription = await registration.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlBase64ToUint8Array(public_key),
      });
      await savePushSubscription(subscription.toJSON());
      setStatus("on");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not turn on notifications. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  async function disable() {
    setBusy(true);
    setError(null);
    try {
      const subscription = await currentPushSubscription();
      if (subscription) {
        await deletePushSubscription(subscription.endpoint);
        await subscription.unsubscribe();
      }
      setStatus("off");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not turn off notifications. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  if (status === "checking") return null;
  const note = NOTES[status];

  return (
    <section className="mt-10">
      <h2 className="text-xl font-medium text-ink">Notifications</h2>
      <p className="mt-1 mb-4 text-small text-muted">
        Get a message on this device when you are registered for an event or a seat opens up for you.
      </p>
      {note ? (
        <p className="text-small text-ink">{note}</p>
      ) : (
        <button
          type="button"
          onClick={status === "on" ? disable : enable}
          disabled={busy}
          className="min-h-11 bg-accent px-5 py-2.5 text-small font-medium text-accent-ink transition-transform duration-150 active:scale-[0.98] disabled:opacity-60"
        >
          {status === "on" ? "Turn off notifications" : "Turn on notifications"}
        </button>
      )}
      {error && (
        <p role="alert" className="mt-2 text-small text-danger">
          {error}
        </p>
      )}
    </section>
  );
}
