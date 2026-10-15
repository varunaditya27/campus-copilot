import * as Sentry from "@sentry/nextjs";
import { privateDataCollection } from "./lib/sentryOptions";

// Errors thrown while the server renders a page are reported too, when SENTRY_DSN is set at run time.
export function register() {
  const dsn = process.env.SENTRY_DSN ?? process.env.NEXT_PUBLIC_SENTRY_DSN;
  if (!dsn) return;
  Sentry.init({
    dsn,
    environment: process.env.SENTRY_ENVIRONMENT ?? "production",
    dataCollection: privateDataCollection,
    tracesSampleRate: 0,
  });
}

export const onRequestError = Sentry.captureRequestError;
