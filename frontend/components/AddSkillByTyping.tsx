"use client";

/**
 * Adding a skill by typing it, on the understanding screen.
 *
 * Every way of adding or correcting a skill used to go back through the
 * microphone: the dashed card said "say something more", and the empty state
 * said "say it again". Both routed to `/speak`. That leaves someone in a noisy
 * room, or on a shared phone, or whose trade was misheard twice, with nothing
 * else to try -- and Tamil is exactly where the mishearing happens.
 *
 * The mic keeps its place as the first thing offered, here as on the landing
 * page, because it asks least of someone who cannot comfortably type. This is
 * the second way, not a replacement.
 *
 * **What the person types is the evidence.** Every skill in this product
 * carries the words that produced it, and the card shows them back. For a
 * typed skill those words are the ones they typed -- which is the same rule
 * the landing page already follows, where typing "joins the pipeline at
 * exactly the point speech does: the transcript". Nothing is attributed to
 * anyone that they did not say, whether they said it aloud or in writing.
 */

import { useState } from "react";

import { copyFor } from "@/lib/i18n";
import type { Language } from "@/lib/types";

export function AddSkillByTyping({
  language,
  busy,
  error,
  onAdd,
}: {
  language: Language;
  busy: boolean;
  /** Shown under the field when the text was not work. */
  error?: string | null;
  /** The typed words. The server decides what they are. */
  onAdd(text: string): void;
}) {
  const copy = copyFor(language);
  const [draft, setDraft] = useState("");

  const submit = () => {
    const text = draft.trim();
    if (!text || busy) return;
    onAdd(text);
    setDraft("");
  };

  return (
    <form
      onSubmit={(event) => {
        event.preventDefault();
        submit();
      }}
      className="flex w-full max-w-[420px] flex-col gap-2"
    >
      <label
        className="text-[13px]"
        style={{ color: "var(--ink-55)" }}
        htmlFor="add-skill"
        lang={language}
      >
        {copy.addByTyping}
      </label>

      <div className="flex gap-2 max-[400px]:flex-col">
        <input
          id="add-skill"
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          placeholder={copy.addSkillPlaceholder}
          disabled={busy}
          lang={language}
          className="min-w-0 flex-1 rounded-full px-4 py-2.5 text-[15px] disabled:opacity-50"
          style={{
            background: "var(--color-surface)",
            border: "1px solid var(--ink-22)",
          }}
        />
        <button
          type="submit"
          disabled={busy || draft.trim() === ""}
          className="vp-pill vp-pill-quiet flex-none justify-center disabled:opacity-40"
          lang={language}
        >
          {busy ? copy.loading : copy.addSkillSubmit}
        </button>
      </div>

      {/* Amber, not red, and beside the field rather than at the top of the
          page. Typing something the system cannot use is a normal part of
          being asked an open question -- not an error the person committed. */}
      {error && (
        <p
          className="vp-rise rounded-[10px] px-3.5 py-2.5 text-[13px] leading-relaxed"
          style={{
            background: "var(--ink-03)",
            color: "var(--color-caution-ink)",
          }}
          role="status"
          lang={language}
        >
          {error}
        </p>
      )}
    </form>
  );
}
