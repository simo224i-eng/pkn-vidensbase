import type { NextConfig } from "next";

// Proxy /api/* til FastAPI-backend'en. Browseren ser kun ét oprindelsessted
// (samme-origin), så auth-cookien fungerer uden cross-origin/SameSite-fiskeri
// — samme opsætning virker uændret i dev og i produktion.
const BACKEND_URL = process.env.BACKEND_URL || "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${BACKEND_URL}/api/:path*` }];
  },
};

export default nextConfig;
