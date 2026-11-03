"use client";

/**
 * The map on "Near you".
 *
 * Leaflet over OpenStreetMap tiles: free, keyless, and open data -- the same
 * reasoning as every other component in the stack. Leaflet touches `window`
 * the moment it is imported, so it is loaded inside an effect and never
 * during the server render.
 *
 * Two kinds of marker, styled differently on purpose:
 *
 *   - Openings are a green bubble with a count, one per town. The record
 *     knows the town, not the street, so one honest pin per town replaces a
 *     stack of pins that would each look like an address.
 *   - Offices from OpenStreetMap are small dots coloured by kind.
 *
 * Every string that reaches a popup is set with `textContent`, never as HTML.
 * OpenStreetMap names are community-edited, and a popup is not a place to
 * trust them with markup.
 */

import { useEffect, useRef, useState } from "react";
import type * as Leaflet from "leaflet";

import type {
  Language,
  NearbyCategory,
  NearbyCentre,
  NearbySchemePlace,
  SupportPlace,
} from "@/lib/types";

export interface MapLabels {
  region: string;
  you: string;
  count: string;
  approx: string;
  km: string;
  directions: string;
  viewOnOsm: string;
  categories: Record<NearbyCategory, string>;
}

export interface MapOpening {
  id: number;
  title: string;
  /** "82%" when this person was matched to it; null otherwise. */
  score: string | null;
}

export interface MapTown {
  place: NearbySchemePlace;
  openings: MapOpening[];
}

/** What to show. `at` changes on every pick, so picking twice re-opens it. */
export interface MapSelection {
  id: string;
  at: number;
}

interface Props {
  centre: NearbyCentre;
  radiusKm: number;
  towns: MapTown[];
  offices: SupportPlace[];
  selected: MapSelection | null;
  language: Language;
  labels: MapLabels;
  onSelect(id: string): void;
  onOpenScheme(id: number): void;
}

const TILE_URL =
  process.env.NEXT_PUBLIC_MAP_TILE_URL ??
  "https://tile.openstreetmap.org/{z}/{x}/{y}.png";

const TILE_ATTRIBUTION =
  '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors';

/** Roughly: the search circle fills the map. */
function zoomFor(radiusKm: number): number {
  if (radiusKm <= 5) return 13;
  if (radiusKm <= 10) return 12;
  return 11;
}

export function townMarkerId(key: string): string {
  return `town:${key}`;
}

export function officeMarkerId(id: string): string {
  return `office:${id}`;
}

/** Directions in whichever maps app the phone has. No key needed. */
export function directionsUrl(lat: number, lng: number): string {
  return `https://www.google.com/maps/dir/?api=1&destination=${lat},${lng}`;
}

function el<K extends keyof HTMLElementTagNameMap>(
  tag: K,
  className = "",
  text?: string,
): HTMLElementTagNameMap[K] {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function externalLink(text: string, href: string): HTMLAnchorElement {
  const link = el("a", "", text);
  link.href = href;
  link.target = "_blank";
  link.rel = "noreferrer noopener";
  return link;
}

export function NearbyMap({
  centre,
  radiusKm,
  towns,
  offices,
  selected,
  language,
  labels,
  onSelect,
  onOpenScheme,
}: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const leafletRef = useRef<typeof Leaflet | null>(null);
  const mapRef = useRef<Leaflet.Map | null>(null);
  const layerRef = useRef<Leaflet.LayerGroup | null>(null);
  const markersRef = useRef<Map<string, Leaflet.Marker>>(new Map());
  const [ready, setReady] = useState(false);

  // Callbacks change identity every render; the markers should not be rebuilt
  // for that, so they read the latest ones through a ref.
  const handlers = useRef({ onSelect, onOpenScheme });
  const selectedRef = useRef<MapSelection | null>(selected);
  useEffect(() => {
    handlers.current = { onSelect, onOpenScheme };
    selectedRef.current = selected;
  });

  // Create the map once. Strict Mode mounts twice in development and the
  // import is async, so a cleanup can run before the map exists -- hence
  // `cancelled`, rather than assuming there is a map to remove.
  useEffect(() => {
    let cancelled = false;
    const markers = markersRef.current;
    void import("leaflet").then((module) => {
      const L = (module as unknown as { default?: typeof Leaflet }).default ?? module;
      if (cancelled || !containerRef.current) return;
      leafletRef.current = L;
      const map = L.map(containerRef.current, {
        // Scrolling the page past the map should scroll the page.
        scrollWheelZoom: false,
      });
      L.tileLayer(TILE_URL, { maxZoom: 19, attribution: TILE_ATTRIBUTION }).addTo(map);
      layerRef.current = L.layerGroup().addTo(map);
      mapRef.current = map;
      setReady(true);
    });
    return () => {
      cancelled = true;
      mapRef.current?.remove();
      mapRef.current = null;
      layerRef.current = null;
      markers.clear();
      setReady(false);
    };
  }, []);

  // Move the view only when where we are looking changes -- not when a
  // category is toggled or the language switched, which would throw away
  // wherever the person had panned to.
  useEffect(() => {
    if (!ready) return;
    mapRef.current?.setView([centre.latitude, centre.longitude], zoomFor(radiusKm));
  }, [ready, centre.latitude, centre.longitude, radiusKm]);

  // Draw (and redraw) everything the props describe.
  useEffect(() => {
    const L = leafletRef.current;
    const layer = layerRef.current;
    if (!ready || !L || !layer) return;

    layer.clearLayers();
    markersRef.current.clear();

    const here: [number, number] = [centre.latitude, centre.longitude];
    L.circle(here, {
      radius: radiusKm * 1000,
      className: "vp-map-radius",
      interactive: false,
    }).addTo(layer);

    // Only when the device said where the person is. A spoken town tells us
    // the town, not the street: a "you" dot at its centre would claim a
    // precision we do not have, so the circle alone marks the area.
    if (centre.source === "gps") {
      L.marker(here, {
        icon: L.divIcon({ className: "vp-map-you", iconSize: [18, 18] }),
        title: labels.you,
        keyboard: false,
        interactive: false,
      }).addTo(layer);
    }

    for (const { place, openings } of towns) {
      if (openings.length === 0) continue;
      const townName = place.names[language] ?? place.names.en ?? place.key;
      const marker = L.marker([place.latitude, place.longitude], {
        icon: L.divIcon({
          className: "vp-map-pin-wrap",
          html: el("span", "vp-map-pin", String(openings.length)),
          iconSize: [34, 34],
          iconAnchor: [17, 17],
        }),
        title: townName,
        zIndexOffset: 500,
      });

      const popup = el("div", "vp-map-popup");
      popup.lang = language;
      popup.append(
        el("strong", "", townName),
        el("span", "vp-map-popup-meta", labels.count.replace("{count}", String(openings.length))),
      );
      const list = el("ul");
      for (const opening of openings) {
        const item = el("li");
        const link = el("a", "", opening.title);
        link.href = `/schemes/${opening.id}`;
        link.addEventListener("click", (event) => {
          event.preventDefault();
          handlers.current.onOpenScheme(opening.id);
        });
        item.append(link);
        if (opening.score) item.append(el("span", "vp-map-popup-score", opening.score));
        list.append(item);
      }
      popup.append(list, el("p", "vp-map-popup-note", labels.approx));

      marker.bindPopup(popup, { maxWidth: 280 });
      marker.on("click", () => handlers.current.onSelect(townMarkerId(place.key)));
      marker.addTo(layer);
      markersRef.current.set(townMarkerId(place.key), marker);
    }

    for (const office of offices) {
      const name = office.names[language] ?? office.name;
      const dot = el("span", "vp-map-dot");
      dot.dataset.cat = office.category;
      const marker = L.marker([office.latitude, office.longitude], {
        icon: L.divIcon({
          className: "vp-map-dot-wrap",
          html: dot,
          iconSize: [16, 16],
          iconAnchor: [8, 8],
        }),
        title: name,
      });

      const popup = el("div", "vp-map-popup");
      popup.lang = language;
      popup.append(
        el("strong", "", name),
        el(
          "span",
          "vp-map-popup-meta",
          `${labels.categories[office.category]} · ${labels.km.replace("{km}", String(office.distance_km))}`,
        ),
      );
      if (office.address) popup.append(el("p", "", office.address));
      if (office.opening_hours) {
        popup.append(el("p", "vp-map-popup-hours", office.opening_hours));
      }
      const links = el("p", "vp-map-popup-links");
      links.append(
        externalLink(labels.directions, directionsUrl(office.latitude, office.longitude)),
        externalLink(labels.viewOnOsm, office.osm_url),
      );
      popup.append(links);

      marker.bindPopup(popup, { maxWidth: 260 });
      marker.on("click", () => handlers.current.onSelect(officeMarkerId(office.id)));
      marker.addTo(layer);
      markersRef.current.set(officeMarkerId(office.id), marker);
    }

    // Redrawing closes every popup. Offices arrive a few seconds after the
    // openings, so without this the one the person just opened would vanish
    // under them. Re-opened in place -- the view is theirs, not ours.
    const current = selectedRef.current;
    if (current) markersRef.current.get(current.id)?.openPopup();
  }, [ready, centre, radiusKm, towns, offices, language, labels]);

  // Picking something in a list shows it on the map. Runs after the draw
  // effect above (declaration order), so the marker it looks for exists.
  useEffect(() => {
    if (!ready || !selected) return;
    const map = mapRef.current;
    const marker = markersRef.current.get(selected.id);
    if (!map || !marker) return;
    map.panTo(marker.getLatLng());
    marker.openPopup();
  }, [ready, selected]);

  return (
    <div
      ref={containerRef}
      className="vp-map h-[clamp(320px,52vh,520px)] w-full overflow-hidden rounded-[16px]"
      role="region"
      aria-label={labels.region}
    />
  );
}
