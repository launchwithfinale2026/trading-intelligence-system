import path from "node:path";
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Pins the workspace root to this directory — without it, Next.js
  // auto-detects a root by scanning for lockfiles and can pick an unrelated
  // one elsewhere on disk if it finds multiple.
  turbopack: {
    root: path.join(__dirname),
  },
};

export default nextConfig;
