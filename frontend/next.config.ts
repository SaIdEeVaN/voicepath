import type { NextConfig } from "next";

/**
 * Security headers for every page (added 2026-11-04).
 *
 * The site used to send none: any page could be framed by another site,
 * sniffed, or made to load scripts and connections from anywhere if something
 * ever injected markup. This is the static policy -- set here, at build time,
 * so pages stay pre-rendered and fast. It still allows inline scripts, which
 * Next.js needs without per-request nonces; everything else is limited to
 * the origins the app actually uses, derived from the same environment
 * variables the app reads so the two cannot drift apart.
 *
 * Origins, and why:
 *   API            NEXT_PUBLIC_API_BASE_URL -- every fetch the app makes.
 *   Map style      NEXT_PUBLIC_MAP_STYLE_URL (OpenFreeMap by default) --
 *                  style JSON, vector tiles, glyphs and sprites.
 *   OSM tiles      tile.openstreetmap.org -- the map's fallback if the style
 *                  cannot load.
 *   Google Fonts   fonts.googleapis.com (CSS) and fonts.gstatic.com (files).
 *   blob:/data:    MapLibre's worker and decoded images; spoken answers are
 *                  played from data: audio.
 */

const isDev = process.env.NODE_ENV === "development";

function originOf(url: string | undefined, fallback: string): string {
  try {
    return new URL(url ?? fallback).origin;
  } catch {
    return new URL(fallback).origin;
  }
}

const apiOrigin = originOf(process.env.NEXT_PUBLIC_API_BASE_URL, "http://localhost:8000");
const mapOrigin = originOf(
  process.env.NEXT_PUBLIC_MAP_STYLE_URL,
  "https://tiles.openfreemap.org/styles/liberty",
);
const osmTiles = "https://tile.openstreetmap.org";

const csp = [
  "default-src 'self'",
  `script-src 'self' 'unsafe-inline'${isDev ? " 'unsafe-eval'" : ""}`,
  "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
  "font-src 'self' data: https://fonts.gstatic.com",
  `img-src 'self' data: blob: ${mapOrigin} ${osmTiles}`,
  `connect-src 'self' ${apiOrigin} ${mapOrigin} ${osmTiles}${isDev ? " ws: http://localhost:*" : ""}`,
  "worker-src 'self' blob:",
  "child-src 'self' blob:",
  "media-src 'self' data: blob:",
  "object-src 'none'",
  "base-uri 'self'",
  "form-action 'self'",
  "frame-ancestors 'none'",
  "manifest-src 'self'",
  // Only when the API is on https, as in production: against a local
  // http://localhost:8000 backend it would upgrade every call and break it.
  ...(apiOrigin.startsWith("https://") ? ["upgrade-insecure-requests"] : []),
].join("; ");

const securityHeaders = [
  { key: "Content-Security-Policy", value: csp },
  { key: "Strict-Transport-Security", value: "max-age=63072000; includeSubDomains" },
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  // The microphone and location are used, by this site only; nothing else is.
  {
    key: "Permissions-Policy",
    value: "camera=(), microphone=(self), geolocation=(self), payment=(), usb=(), browsing-topics=()",
  },
  { key: "Cross-Origin-Opener-Policy", value: "same-origin" },
];

const config: NextConfig = {
  reactStrictMode: true,
  // Says which framework and version to target; nobody else needs to know.
  poweredByHeader: false,
  typescript: { ignoreBuildErrors: false },
  async headers() {
    return [{ source: "/:path*", headers: securityHeaders }];
  },
};

export default config;
