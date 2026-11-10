import { randomUUID } from "node:crypto";
import { createSerwistRoute } from "@serwist/turbopack";

// Builds app/sw.ts into the service worker served at /serwist/sw.js. The offline page is
// stored with a new revision for each build, so a new version replaces the old copy.
export const { dynamic, dynamicParams, revalidate, generateStaticParams, GET } =
  createSerwistRoute({
    additionalPrecacheEntries: [{ url: "/~offline", revision: randomUUID() }],
    swSrc: "app/sw.ts",
    useNativeEsbuild: true,
  });
