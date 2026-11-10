// Where the service worker keeps the signed-in student's last events, conversation and
// identity, so the app can still be read without a connection.
export const API_CACHE = "campus-copilot-api";

// Called when a session ends or someone signs in: what was kept for one person must never be
// readable by the next person who uses the same browser.
export async function clearOfflineData(): Promise<void> {
  if (typeof caches === "undefined") return;
  try {
    await caches.delete(API_CACHE);
  } catch {
    // Nothing useful to do: the browser refused, so there is nothing we can clear.
  }
}
