"use client";

/**
 * The session-dependent half of the detail screen.
 *
 * The score bars translate each component of the match into the person's own
 * terms -- "Your experience", not "experience_score" -- and the number is
 * never labelled as a score. Section 2 forbids showing a match vector score
 * raw; a filled bar next to a plain-language label says the same thing in a
 * form that does not need explaining.
 */

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { AskVoicePath } from "@/components/AskVoicePath";
import { ErrorNote } from "@/components/Notices";
import { ApiError, api } from "@/lib/api";
import { copyFor } from "@/lib/i18n";
import { useSession } from "@/lib/session";
import type { MatchResult, OpportunityDetail } from "@/lib/types";

export function OpportunityView({
  opportunity,
}: {
  opportunity: OpportunityDetail;
}) {
  const router = useRouter();
  const { language, sessionId, matches } = useSession();
  const copy = copyFor(language);

  const [match, setMatch] = useState<MatchResult | null>(null);
  // PRD section 9 defers application tracking, so this cannot submit anything.
  // It reveals the reference the person quotes in person instead -- useful,
  // and honest about what VoicePath does not do.
  const [showApply, setShowApply] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => setHydrated(true), []);

  useEffect(() => {
    if (!hydrated || !sessionId) return;

    const known = matches.find((m) => m.opportunity.id === opportunity.id);
    if (known) {
      setMatch(known);
      return;
    }

    // Read the stored match rather than re-scoring, so the numbers shown are
    // the ones that were computed and persisted for this session.
    let cancelled = false;
    api
      .storedMatch(opportunity.id, sessionId)
      .then((result) => !cancelled && setMatch(result))
      .catch((cause: unknown) => {
        // A 404 just means this opportunity was outside the top results.
        if (!cancelled && cause instanceof ApiError && cause.status !== 404) {
          setError(cause.message);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [hydrated, sessionId, matches, opportunity.id]);

  const bars = match
    ? [
        { label: copy.barSkills, value: match.breakdown.skill_similarity_score },
        { label: copy.barExperience, value: match.breakdown.experience_score },
        { label: copy.barRequirements, value: match.breakdown.eligibility_score },
        { label: copy.barDistance, value: match.breakdown.location_score },
      ]
    : [];

  const pay =
    opportunity.salary_min && opportunity.salary_max
      ? opportunity.salary_min === opportunity.salary_max
        ? `₹${opportunity.salary_min.toLocaleString("en-IN")}`
        : `₹${opportunity.salary_min.toLocaleString("en-IN")}–${opportunity.salary_max.toLocaleString("en-IN")}`
      : opportunity.salary_max
        ? `up to ₹${opportunity.salary_max.toLocaleString("en-IN")}`
        : null;

  return (
    <section className="mx-auto w-full max-w-[1080px] flex-1 px-[7vw] py-[clamp(2rem,5vw,3.5rem)] pb-20">
      <button
        type="button"
        onClick={() => router.push("/opportunities")}
        className="mb-7 flex items-center gap-2 text-[13px] transition-colors"
        style={{ color: "var(--ink-45)" }}
        lang={language}
      >
        <span>←</span>
        {copy.back}
      </button>

      <div className="grid items-start gap-11 lg:grid-cols-[minmax(0,1.35fr)_minmax(0,1fr)]">
        <div>
          <h1 className="vp-display text-[clamp(1.875rem,3.6vw,3rem)] leading-[1.04] tracking-[-0.035em]">
            {opportunity.title}
          </h1>
          <p className="mt-3 text-[15px]" style={{ color: "var(--ink-62)" }}>
            {[opportunity.organization, opportunity.location, opportunity.type].join(
              " · ",
            )}
          </p>

          <div
            className="mt-7 flex flex-col gap-5 rounded-[16px] p-7"
            style={{
              background: "var(--color-surface)",
              border: "1px solid var(--ink-09)",
            }}
          >
            {match ? (
              <>
                <p className="flex items-baseline gap-3">
                  <span
                    className="font-display text-[40px] leading-none tracking-[-0.03em]"
                    style={{ color: "var(--color-accent)" }}
                  >
                    {Math.round(match.overall_score * 100)}%
                  </span>
                  <span className="text-sm" style={{ color: "var(--ink-62)" }} lang={language}>
                    {copy.matchWord}
                  </span>
                </p>

                <ul className="flex flex-col gap-3.5">
                  {bars.map((bar) => (
                    <li key={bar.label} className="flex items-center gap-4">
                      <span
                        className="w-[150px] flex-none text-[13.5px] leading-snug"
                        style={{ color: "var(--ink-70)" }}
                        lang={language}
                      >
                        {bar.label}
                      </span>
                      <span
                        className="block h-[7px] flex-1 overflow-hidden rounded-full"
                        style={{ background: "var(--ink-06)" }}
                      >
                        <span
                          className="block h-full rounded-full transition-[width] duration-500"
                          style={{
                            width: `${Math.round(bar.value * 100)}%`,
                            background: "var(--color-accent)",
                          }}
                        />
                      </span>
                      <span
                        className="font-mono w-9 flex-none text-right text-xs"
                        style={{ color: "var(--ink-45)" }}
                      >
                        {Math.round(bar.value * 100)}
                      </span>
                    </li>
                  ))}
                </ul>

                <ul className="flex flex-col gap-2.5 pt-1">
                  {match.explanation_bullets.map((bullet, index) => (
                    <li
                      key={index}
                      className="flex items-start gap-3 text-[15px] leading-relaxed"
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
              </>
            ) : (
              <p className="text-[15px] leading-relaxed" style={{ color: "var(--ink-80)" }}>
                {opportunity.description}
              </p>
            )}

            {/* Where the words came from. The explanation layer may ground
                itself only in this record, and the reader is told that. */}
            <p
              className="border-t pt-4 text-xs leading-relaxed"
              style={{ borderColor: "var(--ink-09)", color: "var(--ink-45)" }}
              lang={language}
            >
              {copy.fromRecord}
              {opportunity.source_reference && (
                <span className="font-mono"> · {opportunity.source_reference}</span>
              )}
            </p>
          </div>

          {match && opportunity.description && (
            <p
              className="mt-6 max-w-[46em] text-[15px] leading-relaxed"
              style={{ color: "var(--ink-70)" }}
            >
              {opportunity.description}
            </p>
          )}

          <dl className="mt-6 flex flex-wrap gap-x-10 gap-y-3 text-sm">
            {pay && <Fact label="Pay" value={pay} />}
            {opportunity.minimum_experience > 0 && (
              <Fact
                label="Experience asked for"
                value={`${opportunity.minimum_experience} years`}
              />
            )}
            {opportunity.certifications_required.length > 0 && (
              <Fact
                label="Certificates required"
                value={opportunity.certifications_required.join(", ")}
              />
            )}
          </dl>

          {error && (
            <div className="mt-6 max-w-[40em]">
              <ErrorNote message={error} />
            </div>
          )}

          <div className="mt-6 flex flex-wrap gap-3">
            <button
              type="button"
              onClick={() => setShowApply((open) => !open)}
              aria-expanded={showApply}
              className="vp-pill vp-pill-primary"
              lang={language}
            >
              {copy.apply}
            </button>
            <Link href="/passport" className="vp-pill vp-pill-quiet" lang={language}>
              {copy.viewPassport}
            </Link>
          </div>

          {showApply && (
            <div
              className="mt-5 max-w-[40em] rounded-[14px] border p-5"
              style={{ borderColor: "var(--ink-22)", background: "var(--ink-04)" }}
              lang={language}
            >
              <h3 className="vp-display text-[1.125rem]">{copy.applyHow}</h3>
              <p className="mt-3 text-[14px]" style={{ color: "var(--ink-62)" }}>
                {opportunity.organization}
                {opportunity.location ? ` · ${opportunity.location}` : ""}
              </p>
              {opportunity.source_reference && (
                <>
                  <p
                    className="mt-4 text-[13px] uppercase tracking-[0.08em]"
                    style={{ color: "var(--ink-45)" }}
                  >
                    {copy.applyRefLabel}
                  </p>
                  <p className="font-mono mt-1.5 text-[15px] tracking-[0.02em]">
                    {opportunity.source_reference}
                  </p>
                </>
              )}
              <p
                className="mt-4 text-[13.5px] leading-relaxed"
                style={{ color: "var(--ink-55)" }}
              >
                {copy.applyNote}
              </p>
            </div>
          )}
        </div>

        <AskVoicePath opportunityId={opportunity.id} />
      </div>
    </section>
  );
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="vp-label">{label}</dt>
      <dd className="mt-1" style={{ color: "var(--ink-80)" }}>
        {value}
      </dd>
    </div>
  );
}
