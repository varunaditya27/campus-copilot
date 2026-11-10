import { deletePushSubscription } from "./api";

// A browser's push subscription, if this one has agreed to notifications.
export async function currentPushSubscription(): Promise<PushSubscription | null> {
  if (!("serviceWorker" in navigator) || !("PushManager" in window)) return null;
  const registration = await navigator.serviceWorker.getRegistration();
  return registration ? registration.pushManager.getSubscription() : null;
}

// The key the push service needs comes as URL-safe base64; the browser wants raw bytes.
export function urlBase64ToUint8Array(base64: string): Uint8Array<ArrayBuffer> {
  const padded = base64 + "=".repeat((4 - (base64.length % 4)) % 4);
  const raw = atob(padded.replace(/-/g, "+").replace(/_/g, "/"));
  return Uint8Array.from(raw, (char) => char.charCodeAt(0));
}

// Called before signing out, so this browser stops getting the previous student's notifications.
export async function removePushSubscription(): Promise<void> {
  try {
    const subscription = await currentPushSubscription();
    if (!subscription) return;
    await deletePushSubscription(subscription.endpoint);
    await subscription.unsubscribe();
  } catch {
    // Signing out must not fail because of this.
  }
}
