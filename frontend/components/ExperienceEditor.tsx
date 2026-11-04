"use client";

/**
 * How long they have worked: shown where it can be checked, and correctable.
 *
 * It is a quarter of a match score. It used to appear nowhere on this screen,
 * so a transcript read as two years when the person said six was scored on
 * two; then it appeared but could only be fixed by recording everything
 * again. Now "Change" opens a number field in place, and saving it clears the
 * stored ranking, so /schemes ranks again on the corrected number.
 *
 * A whole number of years is what people say, but half years are allowed
 * ("six months" is 0.5); the server keeps one decimal place and refuses
 * anything outside 0-70, the same bound extraction applies to speech.
 */

import { useState } from "react";

import { ApiError, api } from "@/lib/api";
import { copyFor } from "@/lib/i18n";
import type { ExtractedProfile, Language } from "@/lib/types";

export function ExperienceEditor({
  language,
  sessionId,
  profile,
  onSaved,
}: {
  language: Language;
  sessionId: string;
  profile: ExtractedProfile | null;
  onSaved(profile: ExtractedProfile): void;
}) {
  const copy = copyFor(language);
  const years = profile?.experience_years ?? null;

  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const open = () => {
    setDraft(years != null ? String(years) : "");
    setError(null);
    setEditing(true);
  };

  const save = async () => {
    const clean = draft.trim().replace(",", ".");
    const value = clean === "" ? null : Number(clean);
    if (value !== null && (!Number.isFinite(value) || value < 0 || value > 70)) {
      setError(copy.experienceInvalid);
      return;
    }
    if (value === years) {
      setEditing(false);
      return;
    }
    setSaving(true);
    setError(null);
    try {
      onSaved(await api.correctExperience(sessionId, value));
      setEditing(false);
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : copy.somethingWentWrong);
    } finally {
      setSaving(false);
    }
  };

  if (editing) {
    return (
      <form
        // Our own check, not the browser's: its message is in the browser's
        // language, not the one on screen.
        noValidate
        className="mt-5 flex flex-col gap-2"
        onSubmit={(event) => {
          event.preventDefault();
          void save();
        }}
      >
        <label
          htmlFor="experience-years"
          className="text-[13px]"
          style={{ color: "var(--ink-55)" }}
          lang={language}
        >
          {copy.experienceLabel}
        </label>
        <div className="flex flex-wrap items-center gap-2">
          <input
            id="experience-years"
            type="number"
            inputMode="decimal"
            min={0}
            max={70}
            step={0.5}
            autoFocus
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            disabled={saving}
            className="w-[6.5rem] rounded-full px-4 py-2.5 text-[17px] disabled:opacity-50"
            style={{
              background: "var(--color-surface)",
              border: "1px solid var(--ink-22)",
            }}
          />
          <button
            type="submit"
            disabled={saving}
            className="vp-pill vp-pill-primary !px-5 !py-2.5 disabled:opacity-50"
            lang={language}
          >
            {saving ? copy.loading : copy.experienceSave}
          </button>
          <button
            type="button"
            disabled={saving}
            onClick={() => setEditing(false)}
            className="vp-pill vp-pill-quiet !px-5 !py-2.5 disabled:opacity-50"
            lang={language}
          >
            {copy.experienceCancel}
          </button>
        </div>
        <p className="text-[12.5px]" style={{ color: "var(--ink-45)" }} lang={language}>
          {copy.experienceRematch}
        </p>
        {error && (
          <p
            className="text-[13px]"
            style={{ color: "var(--color-caution-ink)" }}
            role="status"
            lang={language}
          >
            {error}
          </p>
        )}
      </form>
    );
  }

  return (
    <div className="mt-5 flex flex-wrap items-baseline gap-2.5">
      {years != null ? (
        <>
          <span
            className="font-display text-[22px] leading-none tracking-[-0.02em]"
            lang={language}
          >
            {copy.experienceHeard.replace("{years}", String(years))}
          </span>
          {profile?.experience_context ? (
            <span
              className="text-[13.5px] italic"
              style={{ color: "var(--ink-55)" }}
              lang={language}
            >
              &ldquo;{profile.experience_context}&rdquo;
            </span>
          ) : null}
        </>
      ) : (
        <span
          className="text-[13.5px]"
          style={{ color: "var(--color-caution-ink)" }}
          lang={language}
        >
          {copy.experienceNotHeard}
        </span>
      )}
      <button
        type="button"
        onClick={open}
        className="text-[13px] underline underline-offset-4"
        style={{ color: "var(--color-accent-deep)" }}
        lang={language}
      >
        {years != null ? copy.experienceChange : copy.experienceAdd}
      </button>
    </div>
  );
}
