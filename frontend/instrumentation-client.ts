import * as Sentry from "@sentry/nextjs";
import { privateDataCollection } from "./lib/sentryOptions";

// Reports errors in the browser to Sentry when NEXT_PUBLIC_SENTRY_DSN was set at build time.
// No personal data is attached (see lib/sentryOptions.ts), and no tracing or session replay is switched on.
const dsn = process.env.NEXT_PUBLIC_SENTRY_DSN;

if (dsn) {
  Sentry.init({
    dsn,
    environment: process.env.NEXT_PUBLIC_SENTRY_ENVIRONMENT ?? "production",
    dataCollection: privateDataCollection,
    tracesSampleRate: 0,
  });
}

export const onRouterTransitionStart = Sentry.captureRouterTransitionStart;
