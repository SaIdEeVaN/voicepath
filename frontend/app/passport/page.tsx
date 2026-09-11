"use client";

/**
 * Skill Passport (PRD sections 5 and 7).
 *
 * A record of the person's working life in their own words, and the one place
 * the audio-retention choice lives. The toggle is off, and the copy next to it
 * says what turning it on means in plain language -- not "consent to data
 * processing", but "employers can hear you say it".
 */

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import { ErrorNote } from "@/components/Notices";
import { ApiError, api } from "@/lib/api";
import { copyFor, skillLabel } from "@/lib/i18n";
import { useSession } from "@/lib/session";

export default function PassportPage() {
  const router = useRouter();
  const {
    language,
    sessionId,
    skills,
    profile,
    audioRetained,
    setAudioRetained,
  } = useSession();
  const copy = copyFor(language);

  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
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

  const toggleRetention = async () => {
    if (!sessionId) return;
    const next = !audioRetained;
    setBusy(true);
    setError(null);
    try {
      const updated = await api.setAudioRetention(sessionId, next);
      setAudioRetained(updated.audio_retained);
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : "Something went wrong.");
    } finally {
      setBusy(false);
    }
  };

  if (!hydrated) return null;

  return (
    <section className="mx-auto w-full max-w-[1080px] flex-1 px-[7vw] py-[clamp(2rem,5vw,3.5rem)] pb-20">
      <article
        className="overflow-hidden rounded-[20px]"
        style={{
          border: "1px solid var(--ink-09)",
          background: "var(--color-surface)",
        }}
      >
        <header
          className="flex flex-wrap items-start justify-between gap-10 px-10 py-9"
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
                className="flex flex-wrap items-center gap-5 rounded-xl px-4.5 py-4"
                style={{ background: "var(--ink-03)", padding: "1rem 1.125rem" }}
              >
                <div className="min-w-[190px] flex-none">
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
                  className="min-w-[220px] flex-1 text-sm leading-snug"
                  style={{ color: "var(--ink-62)" }}
                  lang={language}
                >
                  &ldquo;{skill.evidence_phrase}&rdquo;
                </blockquote>
              </li>
            ))}
          </ul>

          {error && <ErrorNote message={error} />}

          {/* The retention opt-in. Off by default, and the label says what it
              does rather than what it is called. */}
          <div
            className="flex flex-wrap items-center gap-5 rounded-xl px-5 py-4.5"
            style={{ border: "1px solid var(--ink-09)", padding: "1.125rem 1.25rem" }}
          >
            <button
              type="button"
              role="switch"
              aria-checked={audioRetained}
              disabled={busy}
              onClick={() => void toggleRetention()}
              className="flex h-7 w-[50px] flex-none rounded-full p-[3px] transition-colors disabled:opacity-50"
              style={{
                background: audioRetained
                  ? "var(--color-accent)"
                  : "var(--ink-12)",
                justifyContent: audioRetained ? "flex-end" : "flex-start",
              }}
            >
              <span
                className="h-[22px] w-[22px] rounded-full"
                style={{
                  background: "var(--color-surface)",
                  boxShadow: "0 1px 3px rgb(0 0 0 / 0.25)",
                }}
              />
              <span className="sr-only">{copy.retainCopy}</span>
            </button>

            <p
              className="min-w-[260px] flex-1 text-sm leading-relaxed"
              style={{ color: "var(--ink-70)" }}
              lang={language}
            >
              {copy.retainCopy}
            </p>

            <span
              className="font-mono text-[11px] tracking-[0.05em]"
              style={{ color: "var(--ink-45)" }}
              lang={language}
            >
              {audioRetained ? copy.retainOn : copy.retainOff}
            </span>
          </div>
        </div>
      </article>

      <div className="mt-6 flex flex-wrap gap-3">
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
          onClick={() => router.push("/understanding")}
          className="vp-pill vp-pill-quiet"
          lang={language}
        >
          {copy.back}
        </button>
      </div>
    </section>
  );
}
