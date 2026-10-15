import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // A self-contained server in .next/standalone, which is what the Docker image runs.
  output: "standalone",
};

export default nextConfig;
