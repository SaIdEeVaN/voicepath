import "maplibre-gl/dist/maplibre-gl.css";

import { NearbyView } from "./NearbyView";

/**
 * Near you: openings on a map, and the offices that can help.
 *
 * `?scheme=7` opens the map on that scheme's town -- the link from a scheme's
 * own page. Read here rather than with `useSearchParams` so the client view
 * receives a plain number and needs no Suspense boundary.
 */
export default async function NearbyPage({
  searchParams,
}: {
  searchParams: Promise<{ scheme?: string | string[] }>;
}) {
  const { scheme } = await searchParams;
  const raw = Array.isArray(scheme) ? scheme[0] : scheme;
  const id = Number(raw);
  return <NearbyView focusSchemeId={Number.isInteger(id) && id > 0 ? id : null} />;
}
