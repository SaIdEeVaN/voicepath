"use client";

/**
 * Ranked scheme feed (PRD section 5).
 *
 * Not a job-board card grid (section 2 rules that out). Each row is a full-
 * width statement: how well it fits, what it is, and why -- with the "why"
 * given equal weight to the title, because the reason is the product.
 *
 * Opened without a session this still works, showing the catalogue unranked.
 * Someone who arrives from a link should see what exists near them rather
 * than a wall telling them to go back and record something.
 */

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { motion, useReducedMotion } from "framer-motion";

import { DegradedNote, ErrorNote } from "@/components/Notices";
import { MatchRing } from "@/components/MatchRing";
import { ApiError, api } from "@/lib/api";
import { copyFor, payLabel, typeLabel } from "@/lib/i18n";
import { useSession } from "@/lib/session";
import type { Language, MatchResult, SchemeSummary } from "@/lib/types";

export default function SchemesPage() {
  const router = useRouter();
  const { language, sessionId, skills, matches, matchesLanguage, setMatches } =
    useSession();
  const copy = copyFor(language);

  const [browse, setBrowse] = useState<SchemeSummary[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hydrated, setHydrated] = useState(false);
  const reduceMotion = useReducedMotion();

  useEffect(() => setHydrated(true), []);

  useEffect(() => {
    if (!hydrated) return;
    let cancelled = false;

    // No session: show the catalogue rather than an empty screen.
    if (!sessionId || skills.length === 0) {
      setLoading(true);
      api
        .schemes()
        .then((result) => !cancelled && setBrowse(result))
        .catch((cause: unknown) => {
          if (!cancelled) {
            setError(
              cause instanceof ApiError ? cause.message : copy.somethingWentWrong,
            );
          }
        })
        .finally(() => !cancelled && setLoading(false));
      return () => {
        cancelled = true;
      };
    }

    // Explanations are prose the server wrote, so switching language has to
    // re-ask it -- a re-render cannot translate a sentence written earlier.
    // The language now lives beside the matches in session state, so every
    // screen reading them can tell whether they are the right ones.
    if (matches.length > 0 && matchesLanguage === language) return;

    setLoading(true);
    api
      .match(sessionId, language)
      .then((result) => {
        if (cancelled) return;
        setMatches(result.matches, language);
      })
      .catch((cause: unknown) => {
        if (!cancelled) {
          setError(
            cause instanceof ApiError ? cause.message : copy.somethingWentWrong,
          );
        }
      })
      .finally(() => !cancelled && setLoading(false));

    return () => {
      cancelled = true;
    };
  }, [
    hydrated,
    sessionId,
    skills.length,
    matches.length,
    matchesLanguage,
    language,
    setMatches,
  ]);

  const open = useCallback(
    (id: number) => router.push(`/schemes/${id}`),
    [router],
  );

  if (!hydrated) return null;

  const ranked = matches.length > 0;

  // `skill_evidence` is the domain's judgment, computed in matching; this is
  // only the interface acting on it.
  const relevant = matches.filter((m) => m.skill_evidence);

  return (
    <section className="mx-auto w-full max-w-[1080px] flex-1 px-[7vw] py-[clamp(2rem,5vw,3.5rem)] pb-20">
      <DegradedNote />

      <h1
        className="vp-display max-w-[20em] text-[clamp(1.875rem,3.4vw,2.875rem)]"
        lang={language}
      >
        {loading ? copy.loading : copy.matchesTitle}
      </h1>
      <p
        className="mt-3 max-w-[36em] text-[14.5px] leading-relaxed"
        style={{ color: "var(--ink-55)" }}
        lang={language}
      >
        {ranked ? copy.matchesSub : copy.fromRecord}
      </p>

      {error && (
        <div className="mt-8 max-w-[46em]">
          <ErrorNote message={error} />
        </div>
      )}

      <div className="mt-10 flex flex-col gap-3">
        {/* Results are filtered, not just sorted.
        
            A scheme that declares no skills cannot be ruled out, and one in a
            different trade scores nothing on skill -- but both still collect
            experience, eligibility and distance, so both used to sit on this
            page at a plausible-looking number. A carpenter was shown a pharma
            job at the top of their results that way.
        
            None of that is why someone comes here. They come to be matched on
            the work they have done, so a result without skill evidence is not
            shown at all, and the empty state says so plainly. */}
        {/* The one orchestrated moment in the product: results arriving in
            rank order, best first. It shows that the list is ordered, which a
            simultaneous appearance does not. Suppressed when the person has
            asked for reduced motion. */}
        {ranked
          ? relevant.map((match, index) => (
              <motion.div
                key={match.scheme.id}
                initial={reduceMotion ? false : { opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{
                  duration: 0.32,
                  delay: reduceMotion ? 0 : Math.min(index * 0.07, 0.5),
                  ease: [0.22, 1, 0.36, 1],
                }}
                className="flex"
              >
                <MatchRow
                  match={match}
                  language={language}
                  onOpen={() => open(match.scheme.id)}
                />
              </motion.div>
            ))
          : (browse ?? []).map((scheme) => (
              <BrowseRow
                language={language}
                key={scheme.id}
                scheme={scheme}
                onOpen={() => open(scheme.id)}
              />
            ))}

        {!loading && ranked && relevant.length === 0 && (
          <p className="text-[15px]" style={{ color: "var(--ink-62)" }} lang={language}>
            {copy.noMatches}
          </p>
        )}

        {!loading && !ranked && (browse?.length ?? 0) === 0 && (
          <p className="text-[15px]" style={{ color: "var(--ink-62)" }} lang={language}>
            {copy.noMatches}
          </p>
        )}
      </div>
    </section>
  );
}

function MatchRow({
  match,
  language,
  onOpen,
}: {
  match: MatchResult;
  language: Language;
  onOpen(): void;
}) {
  const o = match.scheme;
  return (
    <button
      type="button"
      onClick={onOpen}
      className="vp-row flex w-full items-start gap-7 rounded-[16px] p-7 text-left max-[560px]:flex-col max-[560px]:gap-4 max-[560px]:p-5"
    >
      <MatchRing score={match.overall_score} />

      <div className="flex min-w-0 flex-1 flex-col gap-3">
        <div>
          <h2 className="font-display text-2xl leading-tight tracking-[-0.025em]">
            {o.title}
          </h2>
          <p className="mt-1.5 text-[13.5px]" style={{ color: "var(--ink-55)" }}>
            {[o.organization, o.location, typeLabel(o.type, language)].join(
              " · ",
            )}
          </p>
        </div>

        {/* The reasons, not a description. Each is grounded in something the
            person said or something the listing states. */}
        <ul className="flex flex-col gap-1.5">
          {match.explanation_bullets.slice(0, 3).map((bullet, index) => (
            <li
              key={index}
              className="flex items-start gap-2.5 text-[14.5px] leading-snug"
              style={{ color: "var(--ink-80)" }}
              lang={language}
            >
              <span
                className="mt-2 h-[5px] w-[5px] flex-none rounded-full"
                style={{ background: "var(--color-accent)" }}
              />
              {bullet}
            </li>
          ))}
        </ul>
      </div>

      <div className="flex flex-none flex-col items-end gap-2 text-right max-[560px]:w-full max-[560px]:flex-row max-[560px]:items-center max-[560px]:justify-between max-[560px]:text-left">
        <span className="font-display whitespace-nowrap text-[19px] tracking-[-0.02em]">
          {payLabel(o.salary_min, o.salary_max, language)}
        </span>
        <span
          className="font-mono whitespace-nowrap rounded px-2 py-1 text-[11px] tracking-[0.06em]"
          style={{ background: "var(--ink-04)", color: "var(--ink-45)" }}
        >
          {typeLabel(o.type, language)}
        </span>
      </div>
    </button>
  );
}

function BrowseRow({
  scheme,
  language,
  onOpen,
}: {
  scheme: SchemeSummary;
  language: Language;
  onOpen(): void;
}) {
  return (
    <button
      type="button"
      onClick={onOpen}
      className="vp-row flex items-center gap-7 rounded-[16px] p-6 text-left max-[560px]:flex-col max-[560px]:items-start max-[560px]:gap-3 max-[560px]:p-5"
    >
      <div className="min-w-0 flex-1">
        <h2 className="font-display text-xl leading-tight tracking-[-0.025em]">
          {scheme.title}
        </h2>
        <p className="mt-1.5 text-[13.5px]" style={{ color: "var(--ink-55)" }}>
          {[
            scheme.organization,
            scheme.location,
            typeLabel(scheme.type, language),
          ].join(
            " · ",
          )}
        </p>
      </div>
      <span className="font-display whitespace-nowrap text-[17px] tracking-[-0.02em]">
        {payLabel(scheme.salary_min, scheme.salary_max, language)}
      </span>
    </button>
  );
}
