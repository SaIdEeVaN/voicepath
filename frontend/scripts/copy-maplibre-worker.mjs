// Copies MapLibre's web worker into public/ so the map can load it.
//
// MapLibre 6 finds its worker next to its own module file. Inside a Next.js
// bundle that file is a hashed chunk with no worker beside it, so the map
// stays blank. Serving the worker from a fixed path and telling MapLibre
// about it (setWorkerUrl, in components/NearbyMap.tsx) fixes that.
//
// Copied at build time rather than committed, so it always matches the
// installed maplibre-gl version. Runs before `next dev` and `next build`.
import { copyFileSync, mkdirSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const require = createRequire(import.meta.url);
const here = dirname(fileURLToPath(import.meta.url));
const source = join(dirname(require.resolve("maplibre-gl/package.json")), "dist", "maplibre-gl-worker.mjs");
const target = join(here, "..", "public", "maplibre", "maplibre-gl-worker.mjs");

mkdirSync(dirname(target), { recursive: true });
copyFileSync(source, target);
console.log(`maplibre worker -> ${target.replace(join(here, ".."), "")}`);
