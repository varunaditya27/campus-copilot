import type { MetadataRoute } from "next";

// The colours are the app's own: bone for the background, as in the header.
export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "Campus Copilot",
    short_name: "Copilot",
    description:
      "An agentic campus assistant — grounded answers, live tools, and human-confirmed actions.",
    start_url: "/",
    scope: "/",
    display: "standalone",
    background_color: "#ecebe7",
    theme_color: "#ecebe7",
    icons: [
      { src: "/icons/icon-192.png", sizes: "192x192", type: "image/png" },
      { src: "/icons/icon-512.png", sizes: "512x512", type: "image/png" },
      {
        src: "/icons/icon-maskable-512.png",
        sizes: "512x512",
        type: "image/png",
        purpose: "maskable",
      },
    ],
  };
}
