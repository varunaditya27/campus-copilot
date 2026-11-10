/// <reference lib="webworker" />
/// <reference lib="esnext" />
import { defaultCache } from "@serwist/turbopack/worker";
import {
  NetworkFirst,
  NetworkOnly,
  Serwist,
  type PrecacheEntry,
  type RuntimeCaching,
  type SerwistGlobalConfig,
} from "serwist";
import { API_CACHE } from "../lib/offline";

declare global {
  interface WorkerGlobalScope extends SerwistGlobalConfig {
    __SW_MANIFEST: (PrecacheEntry | string)[] | undefined;
  }
}

declare const self: ServiceWorkerGlobalScope;

// What can still be read without a connection: who is signed in, the events, the last conversation.
const READABLE_OFFLINE = /^\/api\/(auth\/me|events(\/[^/]+)?|chat\/history)$/;

// These come before the default rules, which would otherwise keep every other API answer
// (the profile, registrations, the calendar file) for a day.
const apiRules: RuntimeCaching[] = [
  {
    matcher: ({ url }) => READABLE_OFFLINE.test(url.pathname),
    handler: new NetworkFirst({ cacheName: API_CACHE, networkTimeoutSeconds: 5 }),
  },
  {
    matcher: ({ url }) => url.pathname.startsWith("/api/"),
    handler: new NetworkOnly(),
  },
];

const serwist = new Serwist({
  precacheEntries: self.__SW_MANIFEST,
  skipWaiting: true,
  clientsClaim: true,
  navigationPreload: true,
  runtimeCaching: [...apiRules, ...defaultCache],
  fallbacks: {
    entries: [
      {
        url: "/~offline",
        matcher: ({ request }) => request.destination === "document",
      },
    ],
  },
});

serwist.addEventListeners();

self.addEventListener("push", (event) => {
  let message: { title?: string; body?: string; url?: string } = {};
  try {
    message = event.data?.json() ?? {};
  } catch {
    return;
  }
  if (!message.title) return;
  event.waitUntil(
    self.registration.showNotification(message.title, {
      body: message.body,
      icon: "/icons/icon-192.png",
      badge: "/icons/badge-96.png",
      data: { url: message.url ?? "/" },
    }),
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  // Only addresses on this site: the page to open comes from the message.
  const target = new URL(event.notification.data?.url ?? "/", self.location.origin);
  const href = target.origin === self.location.origin ? target.href : self.location.origin;
  event.waitUntil(
    (async () => {
      const windows = await self.clients.matchAll({ type: "window", includeUncontrolled: true });
      const open = windows.find((w) => w.url === href) ?? windows[0];
      if (open) {
        await open.focus();
        if (open.url !== href) await open.navigate(href);
      } else {
        await self.clients.openWindow(href);
      }
    })(),
  );
});
