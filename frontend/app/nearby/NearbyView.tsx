"use client";

/**
 * Near you (the map).
 *
 * Where the map centres, in order of what we actually know:
 *
 *   1. The device location, if the person pressed "Use my location". Rounded
 *      to two decimals (about a kilometre) here, before it leaves the browser,
 *      and held in this component's state only -- never in session storage.
 *   2. A town they picked from the list.
 *   3. The place they said while describing their work.
 *   4. Nothing: then the map shows where the openings are, and says that is
 *      what it is doing rather than pretending to know where they are.
 *
 * Openings and offices load separately. Openings come from the catalogue and
 * are instant; offices come from OpenStreetMap's volunteer servers and can
 * take a while, so the map is useful before they arrive and still useful if
 * they never do.
 *
 * Distances here are information, not ranking. The ranked list on /schemes is
 * the audited one; this screen orders by distance and says so in its heading.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";

import { ErrorNote } from "@/components/Notices";
import {
  NearbyMap,
  directionsUrl,
  officeMarkerId,
  townMarkerId,
  type MapLabels,
  type MapSelection,
  type MapTown,
} from "@/components/NearbyMap";
import { ApiError, api } from "@/lib/api";
import { copyFor, localeFor, typeLabel } from "@/lib/i18n";
import { useSession } from "@/lib/session";
import {
  NEARBY_CATEGORIES,
  type KnownPlace,
  type Language,
  type NearbyCategory,
  type NearbyResponse,
  type SupportResponse,
} from "@/lib/types";

const RADII = [5, 10, 25] as const;
type Radius = (typeof RADII)[number];

type LocationProblem = "denied" | "failed" | null;

/** Two decimals of a degree: about 1.1 km. Done before anything is sent. */
function coarsen(value: number): number {
  return Math.round(value * 100) / 100;
}

/** "2026-11-03" as each language writes a date. Falls back to the ISO form. */
function formatDay(iso: string, language: Language): string {
  const day = new Date(`${iso}T00:00:00Z`);
  if (Number.isNaN(day.getTime())) return iso;
  try {
    return new Intl.DateTimeFormat(localeFor(language), {
      day: "numeric",
      month: "long",
      year: "numeric",
      timeZone: "UTC",
    }).format(day);
  } catch {
    return iso;
  }
}

function nameIn(names: Record<string, string>, language: Language, fallback = ""): string {
  return names[language] || names.en || fallback;
}

export function NearbyView({ focusSchemeId }: { focusSchemeId: number | null }) {
  const router = useRouter();
  const { language, profile, matches } = useSession();
  const copy = copyFor(language);

  const [hydrated, setHydrated] = useState(false);
  const [gps, setGps] = useState<{ latitude: number; longitude: number } | null>(null);
  const [chosen, setChosen] = useState<string | null>(null);
  const [locating, setLocating] = useState(false);
  const [locationProblem, setLocationProblem] = useState<LocationProblem>(null);
  const [radius, setRadius] = useState<Radius>(10);
  const [categories, setCategories] = useState<Set<NearbyCategory>>(
    () => new Set(NEARBY_CATEGORIES),
  );
  const [showAll, setShowAll] = useState<boolean | null>(null);

  const [known, setKnown] = useState<KnownPlace[]>([]);
  const [nearby, setNearby] = useState<NearbyResponse | null>(null);
  const [nearbyError, setNearbyError] = useState<string | null>(null);
  const [support, setSupport] = useState<SupportResponse | null>(null);
  const [supportLoading, setSupportLoading] = useState(false);
  const [selected, setSelected] = useState<MapSelection | null>(null);

  useEffect(() => setHydrated(true), []);

  const spoken = profile?.location ?? null;

  useEffect(() => {
    let cancelled = false;
    api
      .knownPlaces()
      .then((places) => !cancelled && setKnown(places))
      .catch(() => {
        /* The picker is a convenience; the map works without it. */
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // Openings, and where to centre.
  useEffect(() => {
    if (!hydrated) return;
    let cancelled = false;
    setNearbyError(null);
    api
      .nearby(gps ? { latitude: gps.latitude, longitude: gps.longitude } : { place: chosen ?? spoken })
      .then((result) => !cancelled && setNearby(result))
      .catch((cause: unknown) => {
        if (!cancelled) {
          setNearbyError(cause instanceof ApiError ? cause.message : copy.somethingWentWrong);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [hydrated, gps, chosen, spoken, copy.somethingWentWrong]);

  // Offices. All four kinds are asked for at once and filtered here, so
  // toggling a category never costs another trip to a volunteer server.
  const centreLat = nearby?.centre.latitude;
  const centreLng = nearby?.centre.longitude;
  useEffect(() => {
    if (centreLat === undefined || centreLng === undefined) return;
    let cancelled = false;
    setSupportLoading(true);
    setSupport(null);
    api
      .support({
        latitude: centreLat,
        longitude: centreLng,
        radiusKm: radius,
        categories: NEARBY_CATEGORIES,
      })
      .then((result) => !cancelled && setSupport(result))
      .catch(() => {
        // Reported the same way as a server that could not look: the
        // openings still stand, and the person is told the offices did not.
        if (!cancelled) {
          setSupport({
            support_places: [],
            support_status: "unavailable",
            source: null,
            as_of: null,
            radius_km: radius,
            provider: "",
            degraded: true,
            attribution: "",
          });
        }
      })
      .finally(() => !cancelled && setSupportLoading(false));
    return () => {
      cancelled = true;
    };
  }, [centreLat, centreLng, radius]);

  // The person's own results, when they have them. `skill_evidence` is the
  // matcher's judgement of fit; the map only acts on it.
  const scores = useMemo(() => {
    const out = new Map<number, string>();
    for (const match of matches) {
      if (match.skill_evidence) {
        out.set(match.scheme.id, `${Math.round(match.overall_score * 100)}%`);
      }
    }
    return out;
  }, [matches]);
  const hasMatches = scores.size > 0;
  const showingAll = showAll ?? !hasMatches;

  const towns: MapTown[] = useMemo(() => {
    if (!nearby) return [];
    return nearby.scheme_places
      .map((place) => ({
        place,
        openings: place.schemes
          .filter((s) => showingAll || scores.has(s.id))
          .map((s) => ({ id: s.id, title: s.title, score: scores.get(s.id) ?? null })),
      }))
      .filter((town) => town.openings.length > 0);
  }, [nearby, scores, showingAll]);

  // The person's own national matches when they have results; all of them
  // when browsing. Same rule as the pins on the map.
  const nationwide = useMemo(
    () =>
      (nearby?.nationwide_schemes ?? []).filter((s) => showingAll || scores.has(s.id)),
    [nearby, scores, showingAll],
  );

  const offices = useMemo(
    () => (support?.support_places ?? []).filter((p) => categories.has(p.category)),
    [support, categories],
  );

  // Arriving from a scheme's page: open on that scheme's town.
  useEffect(() => {
    if (!nearby || focusSchemeId === null) return;
    const town = nearby.scheme_places.find((p) =>
      p.schemes.some((s) => s.id === focusSchemeId),
    );
    if (!town) return;
    if (!scores.has(focusSchemeId)) setShowAll(true);
    setSelected({ id: townMarkerId(town.key), at: Date.now() });
    // `scores` is left out on purpose: this runs on arrival, and a later
    // change to the person's results should not pull the map back here.
  }, [nearby, focusSchemeId]);

  const useMyLocation = useCallback(() => {
    if (typeof navigator === "undefined" || !navigator.geolocation) {
      setLocationProblem("failed");
      return;
    }
    setLocating(true);
    setLocationProblem(null);
    navigator.geolocation.getCurrentPosition(
      (position) => {
        setLocating(false);
        setChosen(null);
        setGps({
          latitude: coarsen(position.coords.latitude),
          longitude: coarsen(position.coords.longitude),
        });
      },
      (problem) => {
        setLocating(false);
        setLocationProblem(problem.code === problem.PERMISSION_DENIED ? "denied" : "failed");
      },
      // A town-level answer is all this needs, and asking for less is both
      // faster and kinder to the battery.
      { enableHighAccuracy: false, timeout: 15000, maximumAge: 10 * 60 * 1000 },
    );
  }, []);

  const pickTown = useCallback((key: string) => {
    setGps(null);
    setLocationProblem(null);
    setChosen(key || null);
  }, []);

  const toggleCategory = useCallback((category: NearbyCategory) => {
    setCategories((previous) => {
      const next = new Set(previous);
      if (next.has(category)) next.delete(category);
      else next.add(category);
      return next;
    });
  }, []);

  const mapFrameRef = useRef<HTMLDivElement>(null);

  // Picked on the map: just remember it.
  const select = useCallback((id: string) => setSelected({ id, at: Date.now() }), []);

  // Picked in a list below the map: remember it and bring the map back into
  // view, or the popup opens somewhere the person has already scrolled past.
  const selectFromList = useCallback((id: string) => {
    setSelected({ id, at: Date.now() });
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    mapFrameRef.current?.scrollIntoView({
      behavior: reduce ? "auto" : "smooth",
      block: "center",
    });
  }, []);
  const openScheme = useCallback((id: number) => router.push(`/schemes/${id}`), [router]);

  const labels: MapLabels = useMemo(
    () => ({
      region: copy.nearbyTitle,
      you: copy.nearbyYou,
      count: copy.nearbyCount,
      approx: copy.nearbyApprox,
      km: copy.nearbyKm,
      directions: copy.nearbyDirections,
      viewOnOsm: copy.nearbyViewOnOsm,
      categories: copy.nearbyCategories,
    }),
    [copy],
  );

  if (!hydrated) return null;

  const centre = nearby?.centre;
  const centreName = centre ? nameIn(centre.names, language, centre.key ?? "") : "";
  const centreLine = !centre
    ? copy.loading
    : centre.source === "gps"
      ? copy.nearbyCentreGps
      : centre.source === "default"
        ? copy.nearbyCentreDefault
        : (chosen ? copy.nearbyCentreChosen : copy.nearbyCentrePlace).replace(
            "{place}",
            centreName,
          );

  const km = (value: number) => copy.nearbyKm.replace("{km}", String(value));

  const sortedKnown = [...known].sort((a, b) =>
    nameIn(a.names, language).localeCompare(nameIn(b.names, language), language),
  );

  return (
    <section className="mx-auto w-full max-w-[1080px] flex-1 px-[7vw] py-[clamp(2rem,5vw,3.5rem)] pb-20">
      <h1
        className="vp-display max-w-[20em] text-[clamp(1.875rem,3.4vw,2.875rem)]"
        lang={language}
      >
        {copy.nearbyTitle}
      </h1>
      <p
        className="mt-3 max-w-[36em] text-[14.5px] leading-relaxed"
        style={{ color: "var(--ink-55)" }}
        lang={language}
      >
        {copy.nearbySub}
      </p>

      {/* Where we are looking, and how to change it. */}
      <div className="mt-8 flex flex-col gap-4" lang={language}>
        <p
          className="flex items-start gap-2.5 text-[15px] leading-snug"
          style={{ color: centre?.source === "default" ? "var(--color-caution-ink)" : "var(--ink-80)" }}
          role="status"
        >
          <span
            className="mt-1.5 h-2.5 w-2.5 flex-none rounded-full"
            style={{
              background:
                centre?.source === "default" ? "var(--color-caution-mark)" : "var(--color-ink)",
            }}
          />
          {centreLine}
        </p>

        <div className="flex flex-wrap items-center gap-3">
          <button
            type="button"
            onClick={useMyLocation}
            disabled={locating}
            className="vp-pill vp-pill-primary"
          >
            {locating ? copy.nearbyLocating : copy.nearbyUseLocation}
          </button>

          <label className="flex items-center gap-2 text-[13.5px]" style={{ color: "var(--ink-62)" }}>
            <span className="sr-only">{copy.nearbyChooseTown}</span>
            <select
              value={chosen ?? ""}
              onChange={(event) => pickTown(event.target.value)}
              className="vp-select"
            >
              <option value="">{copy.nearbyChooseTown}</option>
              {sortedKnown.map((place) => (
                <option key={place.key} value={place.key}>
                  {nameIn(place.names, language, place.key)}
                </option>
              ))}
            </select>
          </label>

          <label className="flex items-center gap-2 text-[13.5px]" style={{ color: "var(--ink-62)" }}>
            {copy.nearbyWithin}
            <select
              value={radius}
              onChange={(event) => setRadius(Number(event.target.value) as Radius)}
              className="vp-select"
            >
              {RADII.map((value) => (
                <option key={value} value={value}>
                  {km(value)}
                </option>
              ))}
            </select>
          </label>
        </div>

        <p className="max-w-[44em] text-xs leading-relaxed" style={{ color: "var(--ink-45)" }}>
          {copy.nearbyGpsNote}
        </p>

        {locationProblem && (
          <p className="text-[13.5px]" style={{ color: "var(--color-caution-ink)" }} role="alert">
            {locationProblem === "denied" ? copy.nearbyLocationDenied : copy.nearbyLocationFailed}
          </p>
        )}
      </div>

      {nearbyError && (
        <div className="mt-6 max-w-[46em]">
          <ErrorNote message={nearbyError} />
        </div>
      )}

      {/* Filters. Openings are always on; the four kinds of office toggle. */}
      <div className="mt-7 flex flex-wrap gap-2" lang={language}>
        {hasMatches && (
          <div
            className="mr-2 flex gap-1 rounded-full p-[3px]"
            style={{ background: "var(--ink-04)" }}
            role="group"
          >
            {[
              { all: false, label: copy.nearbyYourMatches },
              { all: true, label: copy.nearbyAllOpenings },
            ].map((option) => (
              <button
                key={String(option.all)}
                type="button"
                aria-pressed={showingAll === option.all}
                onClick={() => setShowAll(option.all)}
                className="vp-seg rounded-full px-3.5 py-1.5 text-[13px] font-medium transition-colors"
                style={{
                  background: showingAll === option.all ? "var(--color-surface)" : "transparent",
                  color: showingAll === option.all ? "var(--color-ink)" : "var(--ink-55)",
                  boxShadow:
                    showingAll === option.all ? "0 1px 3px rgb(var(--ink-rgb) / 0.12)" : "none",
                }}
              >
                {option.label}
              </button>
            ))}
          </div>
        )}
        {NEARBY_CATEGORIES.map((category) => {
          const on = categories.has(category);
          return (
            <button
              key={category}
              type="button"
              aria-pressed={on}
              onClick={() => toggleCategory(category)}
              className="vp-chip"
              data-on={on}
            >
              <span className="vp-chip-dot" data-cat={category} />
              {copy.nearbyCategories[category]}
            </button>
          );
        })}
      </div>

      <div ref={mapFrameRef} className="vp-map-frame mt-5">
        {centre ? (
          <NearbyMap
            centre={centre}
            radiusKm={radius}
            towns={towns}
            offices={offices}
            selected={selected}
            language={language}
            labels={labels}
            onSelect={select}
            onOpenScheme={openScheme}
          />
        ) : (
          <div className="vp-map h-[clamp(320px,52vh,520px)] w-full rounded-[16px]" />
        )}
        <p className="mt-2 text-xs" style={{ color: "var(--ink-45)" }} lang={language}>
          {copy.nearbyStraightLine}
        </p>
      </div>

      <div className="mt-10 grid items-start gap-10 lg:grid-cols-2" lang={language}>
        {/* Openings, by town, nearest town first. */}
        <div>
          <h2 className="vp-display text-[1.375rem]">{copy.nearbyOpeningsHeading}</h2>
          <p className="mt-2 text-[13px]" style={{ color: "var(--ink-45)" }}>
            {copy.nearbyApprox}
          </p>

          <ul className="mt-5 flex flex-col gap-3">
            {towns.map(({ place, openings }) => (
              <li
                key={place.key}
                className="rounded-[14px] p-5"
                style={{ background: "var(--color-surface)", border: "1px solid var(--ink-09)" }}
              >
                <button
                  type="button"
                  onClick={() => selectFromList(townMarkerId(place.key))}
                  className="flex w-full items-baseline justify-between gap-3 text-left"
                >
                  <span className="flex items-center gap-2.5">
                    <span className="vp-map-pin vp-map-pin-small" aria-hidden>
                      {openings.length}
                    </span>
                    <span className="font-display text-[17px] tracking-[-0.015em]">
                      {nameIn(place.names, language, place.key)}
                    </span>
                  </span>
                  <span className="font-mono text-[12px]" style={{ color: "var(--ink-45)" }}>
                    {km(place.distance_km)}
                  </span>
                </button>
                <ul className="mt-3 flex flex-col gap-2 border-t pt-3" style={{ borderColor: "var(--ink-09)" }}>
                  {openings.map((opening) => {
                    const ref = place.schemes.find((s) => s.id === opening.id);
                    return (
                      <li key={opening.id} className="flex items-start justify-between gap-3">
                        <button
                          type="button"
                          onClick={() => openScheme(opening.id)}
                          className="min-w-0 text-left"
                        >
                          <span
                            className="block text-[14.5px] leading-snug underline-offset-4 hover:underline"
                            lang="en"
                          >
                            {opening.title}
                          </span>
                          {ref && (
                            <span className="mt-0.5 block text-[12.5px]" style={{ color: "var(--ink-55)" }}>
                              {ref.organization} · {typeLabel(ref.type, language)}
                            </span>
                          )}
                        </button>
                        {opening.score && (
                          <span
                            className="font-mono flex-none text-[12.5px]"
                            style={{ color: "var(--color-accent-deep)" }}
                          >
                            {opening.score}
                          </span>
                        )}
                      </li>
                    );
                  })}
                </ul>
              </li>
            ))}
          </ul>

          {/* National schemes: open wherever the person is, so listed rather
              than pinned -- there is no one place to pin them, and "not on
              the map yet" would read as a gap rather than as everywhere. */}
          {nationwide.length > 0 && (
            <div className="mt-6">
              <h3 className="text-[15px] font-medium">{copy.nearbyNationwide}</h3>
              <p className="mt-1 text-[13px]" style={{ color: "var(--ink-55)" }}>
                {copy.nearbyNationwideNote}
              </p>
              <ul className="mt-3 flex flex-col gap-2">
                {nationwide.map((ref) => (
                  <li key={ref.id} className="flex items-baseline justify-between gap-3">
                    <button
                      type="button"
                      onClick={() => openScheme(ref.id)}
                      className="text-left text-[14px] underline-offset-4 hover:underline"
                      lang="en"
                    >
                      {ref.title}
                      <span className="block text-[12px]" style={{ color: "var(--ink-45)" }}>
                        {ref.organization} · {typeLabel(ref.type, language)}
                      </span>
                    </button>
                    {scores.has(ref.id) && (
                      <span className="font-mono flex-none text-[12px]" style={{ color: "var(--color-accent-deep)" }}>
                        {scores.get(ref.id)}
                      </span>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {nearby && nearby.unplaced_schemes.length > 0 && showingAll && (
            <div className="mt-6">
              <p className="text-[13px]" style={{ color: "var(--ink-55)" }}>
                {copy.nearbyUnplaced}
              </p>
              <ul className="mt-2 flex flex-col gap-1.5">
                {nearby.unplaced_schemes.map((scheme) => (
                  <li key={scheme.id}>
                    <button
                      type="button"
                      onClick={() => openScheme(scheme.id)}
                      className="text-left text-[14px] underline-offset-4 hover:underline"
                      lang="en"
                    >
                      {scheme.title}
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>

        {/* Offices that can help. */}
        <div>
          <h2 className="vp-display text-[1.375rem]">{copy.nearbySupportHeading}</h2>
          <p className="mt-2 text-[13px]" style={{ color: "var(--ink-45)" }}>
            {copy.nearbySupportNote}
          </p>

          {supportLoading && (
            <p className="mt-5 text-[14px]" style={{ color: "var(--ink-55)" }} role="status">
              {copy.thinking}
            </p>
          )}
          {!supportLoading && support?.support_status === "unavailable" && (
            <p className="mt-5 text-[14px]" style={{ color: "var(--color-caution-ink)" }} role="status">
              {copy.nearbySupportUnavailable}
            </p>
          )}
          {!supportLoading && support?.support_status === "offline" && (
            <p className="mt-5 text-[14px]" style={{ color: "var(--ink-55)" }} role="status">
              {copy.nearbySupportOffline}
            </p>
          )}

          {support?.support_status === "ok" &&
            NEARBY_CATEGORIES.filter((c) => categories.has(c)).map((category) => {
              const inCategory = offices.filter((p) => p.category === category);
              return (
                <div key={category} className="mt-6">
                  <h3 className="flex items-center gap-2 text-[14px] font-semibold">
                    <span className="vp-chip-dot" data-cat={category} />
                    {copy.nearbyCategories[category]}
                  </h3>
                  {inCategory.length === 0 ? (
                    <p className="mt-2 text-[13.5px]" style={{ color: "var(--ink-45)" }}>
                      {copy.nearbySupportNone}
                    </p>
                  ) : (
                    <ul className="mt-2 flex flex-col">
                      {inCategory.map((office) => (
                        <li
                          key={office.id}
                          className="flex items-start justify-between gap-3 border-b py-2.5"
                          style={{ borderColor: "var(--ink-06)" }}
                        >
                          <button
                            type="button"
                            onClick={() => selectFromList(officeMarkerId(office.id))}
                            className="min-w-0 text-left"
                          >
                            <span className="block text-[14.5px] leading-snug underline-offset-4 hover:underline">
                              {nameIn(office.names, language, office.name)}
                            </span>
                            {office.address && (
                              <span className="mt-0.5 block text-[12.5px]" style={{ color: "var(--ink-55)" }}>
                                {office.address}
                              </span>
                            )}
                          </button>
                          <span className="flex flex-none flex-col items-end gap-1">
                            <span className="font-mono text-[12px]" style={{ color: "var(--ink-45)" }}>
                              {km(office.distance_km)}
                            </span>
                            <a
                              href={directionsUrl(office.latitude, office.longitude)}
                              target="_blank"
                              rel="noreferrer noopener"
                              className="text-[12.5px] underline underline-offset-4"
                              style={{ color: "var(--color-accent-deep)" }}
                            >
                              {copy.nearbyDirections}
                            </a>
                          </span>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              );
            })}

          {support?.attribution && (
            <p className="mt-6 text-[12px]" style={{ color: "var(--ink-38)" }}>
              {support.attribution}
              {/* The bundled list is a snapshot; say how old, so "this list
                  can be out of date" has a date to it. Rendered only after
                  hydration, so the locale's date format cannot mismatch. */}
              {support.source === "snapshot" && support.as_of && (
                <>
                  {" · "}
                  {copy.nearbySupportAsOf.replace(
                    "{date}",
                    formatDay(support.as_of, language),
                  )}
                </>
              )}
            </p>
          )}
        </div>
      </div>
    </section>
  );
}
