"use client";

/**
 * Low-confidence disambiguation (PRD section 4.3, Error Handling).
 *
 * When normalization cannot clear the confidence threshold, the machine asks
 * instead of guessing. The person's own words are quoted above the choices, so
 * the question is answerable without remembering what they said a minute ago.
 *
 * "Leave it out" is a first-class answer. A skill nobody is sure about is
 * better absent than wrong -- a wrong one sends someone to the wrong district.
 */

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import { ErrorNote } from "@/components/Notices";
import { MicIcon } from "@/components/MicIcon";
import { ApiError, api } from "@/lib/api";
import { copyFor, skillLabel } from "@/lib/i18n";
import { useSession } from "@/lib/session";
import type { SkillEdit } from "@/lib/types";

export default function DisambiguatePage() {
  const router = useRouter();
  const { language, sessionId, skills, setSkills } = useSession();
  const copy = copyFor(language);

  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => setHydrated(true), []);

  const pending = useMemo(
    () => skills.filter((skill) => skill.needs_disambiguation),
    [skills],
  );
  const current = pending[0];

  // Nothing left to ask about: the screen has done its job.
  useEffect(() => {
    if (hydrated && !busy && pending.length === 0) {
      router.replace("/understanding");
    }
  }, [hydrated, busy, pending.length, router]);

  const edits = (): SkillEdit[] =>
    skills.map((skill) => ({
      id: skill.id,
      raw_name: skill.raw_name,
      evidence_phrase: skill.evidence_phrase,
      chosen_skill_id: skill.user_confirmed ? skill.normalized_skill_id : null,
    }));

  const resolve = async (chosenSkillId: number | null) => {
    if (!sessionId || !current) return;
    const index = skills.findIndex((s) => s === current);
    setBusy(true);
    setError(null);
    try {
      const payload = edits().map((edit, i) =>
        i !== index
          ? edit
          : chosenSkillId === null
            ? { ...edit, removed: true }
            : { ...edit, chosen_skill_id: chosenSkillId },
      );
      const result = await api.normalize(sessionId, payload);
      setSkills(result.skills);
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : "Something went wrong.");
    } finally {
      setBusy(false);
    }
  };

  if (!hydrated || !current) return null;

  return (
    <section className="flex flex-1 flex-col items-center justify-center gap-9 px-[7vw] py-[clamp(2rem,5vw,3.5rem)] text-center">
      <div
        className="grid h-[46px] w-[46px] place-items-center rounded-xl"
        style={{
          background: "color-mix(in srgb, var(--color-caution) 18%, transparent)",
        }}
      >
        <span
          className="h-2.5 w-2.5 rotate-45"
          style={{ background: "var(--color-caution-mark)" }}
        />
      </div>

      <div>
        <h1
          className="vp-display mx-auto max-w-[22em] text-[clamp(1.75rem,3.2vw,2.625rem)]"
          lang={language}
        >
          {copy.whichOne}
        </h1>
        <p className="mt-3.5 text-[15px]" style={{ color: "var(--ink-62)" }}>
          <span lang={language}>{copy.youSaid}</span>{" "}
          <span lang={language} style={{ color: "var(--color-ink)" }}>
            &ldquo;{current.evidence_phrase}&rdquo;
          </span>
        </p>
      </div>

      {error && (
        <div className="w-full max-w-[560px]">
          <ErrorNote message={error} />
        </div>
      )}

      <div className="flex flex-wrap justify-center gap-3.5">
        {current.candidates.map((candidate) => (
          <button
            key={candidate.id}
            type="button"
            disabled={busy}
            onClick={() => void resolve(candidate.id)}
            className="flex w-[270px] max-w-full flex-col gap-2.5 rounded-[14px] p-6 text-left transition-all hover:-translate-y-0.5 disabled:opacity-50"
            style={{
              background: "var(--color-surface)",
              border: "1px solid var(--ink-09)",
            }}
            onMouseEnter={(event) => {
              event.currentTarget.style.borderColor = "var(--color-accent)";
            }}
            onMouseLeave={(event) => {
              event.currentTarget.style.borderColor = "var(--ink-09)";
            }}
          >
            <span className="font-display text-[22px] leading-tight tracking-[-0.02em]">
              {skillLabel(candidate, language)}
            </span>
            {candidate.hint && (
              <span
                className="text-sm leading-snug"
                style={{ color: "var(--ink-55)" }}
              >
                {candidate.hint}
              </span>
            )}
          </button>
        ))}
      </div>

      <div className="flex items-center gap-4">
        <button
          type="button"
          onClick={() => router.push("/speak")}
          className="vp-pill vp-pill-quiet text-sm"
          lang={language}
        >
          <MicIcon size={17} strokeWidth={1.5} />
          {copy.resay}
        </button>
        <button
          type="button"
          disabled={busy}
          onClick={() => void resolve(null)}
          className="text-sm transition-colors disabled:opacity-50"
          style={{ color: "var(--ink-45)" }}
          lang={language}
        >
          {copy.skip}
        </button>
      </div>

      {pending.length > 1 && (
        <p className="font-mono text-[11px]" style={{ color: "var(--ink-38)" }}>
          {pending.length - 1} more
        </p>
      )}
    </section>
  );
}
