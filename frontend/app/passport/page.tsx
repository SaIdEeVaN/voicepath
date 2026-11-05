"use client";

/**
 * Skill Passport (PRD sections 5 and 7).
 *
 * A record of the person's working life in their own words.
 *
 * It used to offer "Keep my voice clips so employers can hear me say it". No
 * code path ever kept a clip -- speech is transcribed in memory and discarded
 * -- so the toggle promised something that never happened. Removed
 * 2026-11-05; the page now says plainly what became of the recording.
 *
 * It prints (2026-11-05): a person can take it to an office or an employer,
 * or keep it as a PDF on their phone. The print layout drops the site's own
 * chrome and the controls, keeps every skill with the words that support it,
 * and says at the foot what the record is -- their own words, not a
 * certificate -- so nobody mistakes it for one.
 */

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import { copyFor, localeFor, skillLabel } from "@/lib/i18n";
import { useSession } from "@/lib/session";

export default function PassportPage() {
  const router = useRouter();
  const { language, sessionId, skills, profile } = useSession();
  const copy = copyFor(language);

  const [hydrated, setHydrated] = useState(false);

  useEffect(() => setHydrated(true), []);

  useEffect(() => {
    if (hydrated && !sessionId) router.replace("/speak");
  }, [hydrated, sessionId, router]);

  const stats = useMemo(() => {
    const years = profile?.experience_years;
    return [
      years != null
        ? { value: String(years), label: copy.statYears }
        : null,
      { value: String(skills.length), label: copy.statSkills },
      { value: language.toUpperCase(), label: copy.statLanguages },
    ].filter((entry): entry is { value: string; label: string } => entry !== null);
  }, [profile, skills.length, language, copy]);

  const today = useMemo(() => {
    try {
      return new Intl.DateTimeFormat(localeFor(language), {
        day: "numeric",
        month: "long",
        year: "numeric",
      }).format(new Date());
    } catch {
      return new Date().toISOString().slice(0, 10);
    }
  }, [language]);

  if (!hydrated) return null;

  return (
    <section className="mx-auto w-full max-w-[1080px] flex-1 px-[7vw] py-[clamp(2rem,5vw,3.5rem)] pb-20 print:max-w-none print:p-0">
      <article
        className="vp-passport overflow-hidden rounded-[20px]"
        style={{
          border: "1px solid var(--ink-09)",
          background: "var(--color-surface)",
        }}
      >
        <header
          className="vp-passport-head flex flex-wrap items-start justify-between gap-10 px-10 py-9"
          style={{ background: "var(--color-accent)", color: "var(--color-paper)" }}
        >
          <div>
            <p className="font-mono text-[11px] tracking-[0.14em] opacity-75">
              {copy.passportLabel}
            </p>
            <h1
              className="font-display mt-3 max-w-[18em] text-[clamp(1.75rem,3.4vw,2.75rem)] leading-[1.05] tracking-[-0.03em]"
              lang={language}
              style={{ textWrap: "pretty" }}
            >
              {copy.passportTitle}
            </h1>
          </div>

          <dl className="flex flex-none gap-9">
            {stats.map((stat) => (
              <div key={stat.label}>
                <dd className="font-display text-[38px] leading-none tracking-[-0.03em]">
                  {stat.value}
                </dd>
                <dt
                  className="mt-2 max-w-[9em] text-xs leading-snug opacity-80"
                  lang={language}
                >
                  {stat.label}
                </dt>
              </div>
            ))}
          </dl>
        </header>

        <div className="flex flex-col gap-7 px-10 py-9">
          <ul className="flex flex-col gap-3">
            {skills.map((skill, index) => (
              <li
                key={skill.id ?? index}
                className="vp-passport-skill flex flex-wrap items-center gap-5 rounded-xl px-4.5 py-4"
                style={{ background: "var(--ink-03)", padding: "1rem 1.125rem" }}
              >
                <div className="min-w-0 basis-[190px] flex-none max-[560px]:basis-full">
                  <p
                    className="font-display text-[18px] tracking-[-0.015em]"
                    lang={language}
                  >
                    {skillLabel(skill, language)}
                  </p>
                  <p
                    className="font-mono mt-1 text-[10.5px] tracking-[0.05em]"
                    style={{ color: "var(--ink-38)" }}
                  >
                    {skill.normalized_code ?? "—"}
                  </p>
                </div>

                <blockquote
                  className="min-w-0 flex-1 basis-[220px] text-sm leading-snug"
                  style={{ color: "var(--ink-62)" }}
                  lang={language}
                >
                  &ldquo;{skill.evidence_phrase}&rdquo;
                </blockquote>
              </li>
            ))}
          </ul>

          {/* What became of the recording -- the only true answer is "nothing
              kept", so that is what it says. Not printed: the footer says
              what the paper is. */}
          <p
            className="max-w-[44em] text-sm leading-relaxed print:hidden"
            style={{ color: "var(--ink-62)" }}
            lang={language}
          >
            {copy.passportVoiceNote}
          </p>

          {/* Only on paper: when this was recorded, and what it is not. */}
          <footer
            className="hidden text-[12px] leading-relaxed print:block"
            style={{ color: "var(--ink-62)" }}
            lang={language}
          >
            <p>{copy.passportRecordedOn.replace("{date}", today)}</p>
            <p className="mt-1">{copy.passportNotCertificate}</p>
          </footer>
        </div>
      </article>

      <div className="mt-6 flex flex-wrap items-center gap-3 print:hidden">
        <button
          type="button"
          onClick={() => router.push("/schemes")}
          className="vp-pill vp-pill-primary"
          lang={language}
        >
          {copy.matchesTitle}
          <span className="text-[17px]">→</span>
        </button>
        <button
          type="button"
          onClick={() => window.print()}
          className="vp-pill vp-pill-quiet"
          lang={language}
          disabled={skills.length === 0}
        >
          {copy.passportPrint}
        </button>
        <button
          type="button"
          onClick={() => router.push("/understanding")}
          className="vp-pill vp-pill-quiet"
          lang={language}
        >
          {copy.back}
        </button>
      </div>
      {skills.length > 0 && (
        <p
          className="mt-3 text-[13px] leading-snug print:hidden"
          style={{ color: "var(--ink-45)" }}
          lang={language}
        >
          {copy.passportPrintHint}
        </p>
      )}
    </section>
  );
}
