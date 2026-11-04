"use client";

/**
 * The map on "Near you".
 *
 * MapLibre GL drawing OpenFreeMap's "Liberty" style: vector tiles built from
 * current OpenStreetMap data, free, keyless, sharp at every zoom. It replaced
 * Leaflet over the standard OpenStreetMap tiles, which were just as current
 * but looked like a map from another decade, and could only label places in
 * whatever language the local `name` tag happened to be in.
 *
 * Labels follow the interface language: Tamil names on a Tamil page, Hindi on
 * a Hindi page, falling back to the local name where OpenStreetMap has no
 * translation. That needs MapLibre 6.15 or later -- earlier versions drew
 * Tamil without reordering its vowel signs, so சேலம் came out as சலேம்.
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
import type * as MapLibre from "maplibre-gl";

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

const STYLE_URL =
  process.env.NEXT_PUBLIC_MAP_STYLE_URL ?? "https://tiles.openfreemap.org/styles/liberty";

/** Served by scripts/copy-maplibre-worker.mjs; see the note there. */
const WORKER_URL = "/maplibre/maplibre-gl-worker.mjs";

/**
 * Plain OpenStreetMap tiles, used only if the vector style cannot be loaded.
 * A dated-looking map is better than a blank grey box with pins floating on it.
 */
const FALLBACK_STYLE: MapLibre.StyleSpecification = {
  version: 8,
  sources: {
    osm: {
      type: "raster",
      tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
      tileSize: 256,
      maxzoom: 19,
      attribution:
        '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    },
  },
  layers: [{ id: "osm", type: "raster", source: "osm" }],
};

const RADIUS_SOURCE = "vp-radius";

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

/** A circle as a polygon, for the search radius. */
function circle(lat: number, lng: number, km: number, steps = 72): GeoJSON.Feature {
  const ring: [number, number][] = [];
  const dLat = km / 110.574;
  const dLng = km / (111.32 * Math.cos((lat * Math.PI) / 180));
  for (let i = 0; i <= steps; i += 1) {
    const t = (i / steps) * 2 * Math.PI;
    ring.push([lng + dLng * Math.cos(t), lat + dLat * Math.sin(t)]);
  }
  return { type: "Feature", properties: {}, geometry: { type: "Polygon", coordinates: [ring] } };
}

function bounds(lat: number, lng: number, km: number): [[number, number], [number, number]] {
  const dLat = km / 110.574;
  const dLng = km / (111.32 * Math.cos((lat * Math.PI) / 180));
  return [
    [lng - dLng, lat - dLat],
    [lng + dLng, lat + dLat],
  ];
}

/**
 * A design token as a colour MapLibre can parse.
 *
 * The tokens are oklch(), which MapLibre's colour parser does not read, and
 * hardcoding a hex here would fork the palette. Painting one pixel with the
 * token and reading it back gives the browser's own conversion.
 */
function token(name: string, fallback: string): string {
  try {
    const value = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
    if (!value) return fallback;
    const canvas = document.createElement("canvas");
    canvas.width = canvas.height = 1;
    const ctx = canvas.getContext("2d", { willReadFrequently: true });
    if (!ctx) return fallback;
    ctx.fillStyle = value;
    ctx.fillRect(0, 0, 1, 1);
    const [r, g, b] = ctx.getImageData(0, 0, 1, 1).data;
    return `rgb(${r}, ${g}, ${b})`;
  } catch {
    return fallback;
  }
}

/**
 * Point every place-name label at the reader's language.
 *
 * Only labels built from a name are touched: road numbers on shields, house
 * numbers and the like keep their own fields. The original expressions are
 * kept so the choice is always made from the style's own, never from a label
 * this function already rewrote.
 */
function applyLanguage(
  map: MapLibre.Map,
  language: Language,
  originals: Map<string, unknown>,
): void {
  const label: MapLibre.ExpressionSpecification =
    language === "en"
      ? ["coalesce", ["get", "name:en"], ["get", "name:latin"], ["get", "name"]]
      : ["coalesce", ["get", `name:${language}`], ["get", "name"]];

  for (const layer of map.getStyle()?.layers ?? []) {
    if (layer.type !== "symbol") continue;
    if (!originals.has(layer.id)) {
      originals.set(layer.id, map.getLayoutProperty(layer.id, "text-field"));
    }
    const original = originals.get(layer.id);
    if (!original || !JSON.stringify(original).includes("name")) continue;
    map.setLayoutProperty(layer.id, "text-field", label);
  }
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
  const libRef = useRef<typeof MapLibre | null>(null);
  const mapRef = useRef<MapLibre.Map | null>(null);
  const markersRef = useRef<Map<string, MapLibre.Marker>>(new Map());
  const originalsRef = useRef<Map<string, unknown>>(new Map());
  // The marker most recently clicked on the map, until its selection lands.
  const clickedRef = useRef<string | null>(null);
  const [ready, setReady] = useState(false);
  // Bumped whenever a style finishes loading, so the radius and the labels
  // are put back after a style swap (the fallback) wipes them.
  const [styleEpoch, setStyleEpoch] = useState(0);

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
    const originals = originalsRef.current;

    void import("maplibre-gl").then((lib) => {
      if (cancelled || !containerRef.current) return;
      libRef.current = lib;
      lib.setWorkerUrl(WORKER_URL);

      const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      const map = new lib.Map({
        container: containerRef.current,
        style: STYLE_URL,
        center: [centre.longitude, centre.latitude],
        zoom: 11,
        // Scrolling the page past the map should scroll the page; a two-finger
        // drag should not tilt or spin a map nobody needs tilted.
        scrollZoom: false,
        dragRotate: false,
        pitchWithRotate: false,
        touchPitch: false,
        fadeDuration: reduceMotion ? 0 : 300,
        attributionControl: { compact: true },
      });
      map.touchZoomRotate.disableRotation();
      map.addControl(new lib.NavigationControl({ showCompass: false }), "top-left");

      // The vector style is served by a free community service. If the style
      // itself cannot be fetched, swap to plain OpenStreetMap tiles once,
      // rather than leave pins floating over nothing.
      //
      // Only a failure *before* the style has loaded counts. A single tile
      // timing out later is normal and must not throw the whole map over --
      // and map.isStyleLoaded() cannot tell the two apart, because it stays
      // false while any tile is still downloading.
      let styleLoaded = false;
      let fellBack = false;
      map.on("error", (event) => {
        if (fellBack || styleLoaded) return;
        fellBack = true;
        console.warn("Map style unavailable; using plain OpenStreetMap tiles", event.error);
        originals.clear();
        map.setStyle(FALLBACK_STYLE);
      });
      map.on("style.load", () => {
        styleLoaded = true;
        setStyleEpoch((n) => n + 1);
      });
      map.once("load", () => {
        if (!cancelled) setReady(true);
      });

      mapRef.current = map;
    });

    return () => {
      cancelled = true;
      for (const marker of markers.values()) marker.remove();
      markers.clear();
      originals.clear();
      mapRef.current?.remove();
      mapRef.current = null;
      setReady(false);
    };
    // Created once. The centre it opens on is only a first guess; the view
    // effect below moves it whenever the centre or radius changes.
  }, []);

  // Labels in the reader's language. Re-applied after a style (re)load.
  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map) return;
    applyLanguage(map, language, originalsRef.current);
  }, [ready, language, styleEpoch]);

  // The search circle, in the product's own accent. Re-added after a style
  // swap, which removes every source and layer the old style carried.
  //
  // Gated on the style having loaded (styleEpoch), not on map.isStyleLoaded():
  // that stays false while tiles are still downloading, and the circle was
  // silently skipped on the vector map and never retried.
  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map || styleEpoch === 0) return;
    const shape = circle(centre.latitude, centre.longitude, radiusKm);
    const existing = map.getSource(RADIUS_SOURCE) as MapLibre.GeoJSONSource | undefined;
    if (existing) {
      existing.setData(shape);
      return;
    }
    const accent = token("--color-accent", "rgb(86, 128, 74)");
    map.addSource(RADIUS_SOURCE, { type: "geojson", data: shape });
    map.addLayer({
      id: `${RADIUS_SOURCE}-fill`,
      type: "fill",
      source: RADIUS_SOURCE,
      paint: { "fill-color": accent, "fill-opacity": 0.06 },
    });
    map.addLayer({
      id: `${RADIUS_SOURCE}-line`,
      type: "line",
      source: RADIUS_SOURCE,
      paint: { "line-color": accent, "line-opacity": 0.55, "line-width": 1.5, "line-dasharray": [3, 3] },
    });
  }, [ready, styleEpoch, centre.latitude, centre.longitude, radiusKm]);

  // Move the view only when where we are looking changes -- not when a
  // category is toggled or the language switched, which would throw away
  // wherever the person had panned to.
  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map) return;
    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    map.fitBounds(bounds(centre.latitude, centre.longitude, radiusKm), {
      padding: 24,
      duration: reduceMotion ? 0 : 600,
    });
  }, [ready, centre.latitude, centre.longitude, radiusKm]);

  // Draw (and redraw) every marker the props describe.
  useEffect(() => {
    const lib = libRef.current;
    const map = mapRef.current;
    if (!ready || !lib || !map) return;

    for (const marker of markersRef.current.values()) marker.remove();
    markersRef.current.clear();

    const add = (
      id: string | null,
      element: HTMLElement,
      at: [number, number],
      popup: HTMLElement | null,
      maxWidth = "280px",
    ) => {
      const marker = new lib.Marker({ element, anchor: "center" }).setLngLat(at);
      if (popup) {
        marker.setPopup(new lib.Popup({ offset: 18, maxWidth, closeButton: true }).setDOMContent(popup));
      }
      if (id) {
        element.addEventListener("click", () => {
          // MapLibre opens this marker's own popup when the click reaches the
          // map. Note that it came from here, so the selection effect does not
          // toggle the same popup a second time -- which closed it.
          clickedRef.current = id;
          handlers.current.onSelect(id);
        });
        markersRef.current.set(id, marker);
      }
      marker.addTo(map);
    };

    // Only when the device said where the person is. A spoken town tells us
    // the town, not the street: a "you" dot at its centre would claim a
    // precision we do not have, so the circle alone marks the area.
    if (centre.source === "gps") {
      const you = el("div", "vp-map-you");
      you.setAttribute("aria-label", labels.you);
      you.setAttribute("role", "img");
      add(null, you, [centre.longitude, centre.latitude], null);
    }

    for (const office of offices) {
      const name = office.names[language] ?? office.name;
      const dot = el("button", "vp-map-dot");
      dot.type = "button";
      dot.dataset.cat = office.category;
      dot.setAttribute("aria-label", name);

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

      add(officeMarkerId(office.id), dot, [office.longitude, office.latitude], popup, "260px");
    }

    // Openings last, so their pins sit above the office dots.
    for (const { place, openings } of towns) {
      if (openings.length === 0) continue;
      const townName = place.names[language] ?? place.names.en ?? place.key;
      const pin = el("button", "vp-map-pin", String(openings.length));
      pin.type = "button";
      pin.setAttribute("aria-label", `${townName}: ${labels.count.replace("{count}", String(openings.length))}`);

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

      add(townMarkerId(place.key), pin, [place.longitude, place.latitude], popup);
    }

    // Redrawing removes every popup. Offices arrive a few seconds after the
    // openings, so without this the one the person just opened would vanish
    // under them. Re-opened in place -- the view is theirs, not ours.
    const current = selectedRef.current;
    const reopen = current ? markersRef.current.get(current.id) : undefined;
    if (reopen && !reopen.getPopup()?.isOpen()) reopen.togglePopup();
  }, [ready, centre, towns, offices, language, labels]);

  // Picking something in a list shows it on the map. Runs after the marker
  // effect above (declaration order), so the marker it looks for exists.
  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map || !selected) return;
    // Picked on the map itself: MapLibre has opened its popup already, and
    // the person is looking right at it -- nothing to move or open.
    if (clickedRef.current === selected.id) {
      clickedRef.current = null;
      return;
    }
    const marker = markersRef.current.get(selected.id);
    if (!marker) return;
    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    map.easeTo({ center: marker.getLngLat(), duration: reduceMotion ? 0 : 500 });
    for (const other of markersRef.current.values()) {
      if (other !== marker && other.getPopup()?.isOpen()) other.togglePopup();
    }
    if (!marker.getPopup()?.isOpen()) marker.togglePopup();
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
