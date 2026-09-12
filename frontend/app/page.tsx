"use client";

/**
 * Landing (PRD section 5).
 *
 * The hero is the statement and the microphone, nothing else. The other two
 * languages sit underneath as their own sentences rather than as a dropdown,
 * so a person who cannot read the language currently showing can still see
 * their own and press it.
 */

import { useState } from "react";
import { useRouter } from "next/navigation";

import { MicIcon } from "@/components/MicIcon";
import { ApiError, api } from "@/lib/api";
import { PrivacyNote } from "@/components/Notices";
import { COPY, LANGUAGES, copyFor } from "@/lib/i18n";
import { useSession } from "@/lib/session";
import type { Language } from "@/lib/types";

export default function LandingPage() {
  const router = useRouter();
  const { language, setLanguage, setSession } = useSession();
  const copy = copyFor(language);

  const [typed, setTyped] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const others = LANGUAGES.filter((entry) => entry.code !== language);

  const start = (chosen: Language) => {
    setLanguage(chosen);
    router.push("/speak");
  };

  /**
   * Typing is a third way in, not a lesser one.
   *
   * It joins the pipeline at exactly the point speech does: the transcript.
   * Everything downstream -- extraction, the evidence check, normalisation,
   * matching -- runs identically, so a typed sentence is held to the same rule
   * that nothing may be attributed to someone that they did not say.
   */
  const submitTyped = async () => {
    const text = typed.trim();
    if (!text || sending) return;
    setSending(true);
    setError(null);
    try {
      const result = await api.clientTranscript(text, language);
      setSession(result.session_id, result.transcript, language);
      router.push("/understanding");
    } catch (cause) {
      setError(
        cause instanceof ApiError ? cause.message : copy.somethingWentWrong,
      );
      setSending(false);
    }
  };

  return (
    <div className="flex flex-1 flex-col">
      {/* Not `flex-1`. The hero used to absorb every spare pixel of a tall
          screen, which centred it beautifully and left the page empty above
          and below. Sized to its content, what follows is visible without
          scrolling on a desktop and one short scroll on a phone.
          `items-center` stays: it aligns the mic against the statement. */}
      <section className="grid items-center gap-16 px-[7vw] py-[clamp(2.5rem,6vw,4.5rem)] lg:grid-cols-[minmax(0,1.15fr)_minmax(0,0.85fr)]">
      <div>
        <h1
          className="vp-statement vp-enter max-w-[13em]"
          style={{ "--vp-delay": "60ms" } as React.CSSProperties}
          lang={language}
        >
          {copy.statement}
        </h1>

        {/* The same promise in three scripts is the most distinctive thing on
            this page, so it arrives as its own beat rather than as a footnote
            under the headline. Pressing one switches and starts, so a wrong
            default costs one tap, not a hunt. */}
        <div className="mt-9 flex max-w-[520px] flex-col gap-0.5">
          {others.map((entry, index) => (
            <button
              key={entry.code}
              type="button"
              onClick={() => start(entry.code)}
              className="vp-enter flex items-baseline gap-3.5 border-t py-3 text-left transition-opacity hover:opacity-60"
              style={
                {
                  borderColor: "var(--ink-09)",
                  "--vp-delay": `${320 + index * 90}ms`,
                } as React.CSSProperties
              }
            >
              <span
                className="font-mono w-6 flex-none text-[10.5px] tracking-[0.08em]"
                style={{ color: "var(--ink-38)" }}
              >
                {entry.label}
              </span>
              <span
                className="text-base leading-snug"
                style={{ color: "var(--ink-62)" }}
                lang={entry.code}
              >
                {COPY[entry.code].statement}
              </span>
            </button>
          ))}
        </div>
      </div>

      <div className="flex flex-col items-center gap-7">
        {/* The mic is where this product spends its boldness. Everything else
            on the page stays quiet so that this reads as the thing to do. */}
        <div
          className="vp-enter relative grid place-items-center"
          style={{ "--vp-delay": "180ms" } as React.CSSProperties}
        >
          {/* A soft field behind it, so the button sits in something rather
              than on a flat page. Not a gradient wash across the section --
              it belongs to the mic and moves nowhere. */}
          <span
            aria-hidden
            className="pointer-events-none absolute h-[300px] w-[300px] rounded-full"
            style={{
              background:
                "radial-gradient(circle, color-mix(in srgb, var(--color-accent) 13%, transparent) 0%, transparent 68%)",
            }}
          />

          <button
            type="button"
            onClick={() => start(language)}
            className="vp-mic relative grid h-[196px] w-[196px] place-items-center rounded-full"
            style={{
              background: "var(--color-accent)",
              color: "var(--color-paper)",
              boxShadow:
                "0 18px 44px -20px color-mix(in srgb, var(--color-accent) 65%, transparent)",
            }}
          >
            {/* Two rings, half a cycle apart: sound leaving the mic rather
                than a border that pulses. They quicken on hover and focus,
                which is the product answering someone about to press it. */}
            <span
              aria-hidden
              className="vp-listen pointer-events-none absolute -inset-1.5 rounded-full border"
              style={{ borderColor: "var(--color-accent)" }}
            />
            <span
              aria-hidden
              className="vp-listen pointer-events-none absolute -inset-1.5 rounded-full border"
              style={{
                borderColor: "var(--color-accent)",
                animationDelay: "1.8s",
              }}
            />
            <MicIcon size={52} />
            <span className="sr-only">{copy.speakHint}</span>
          </button>
        </div>

        <p
          className="max-w-[16em] text-center text-[17px] leading-snug"
          style={{ color: "var(--ink-70)" }}
          lang={language}
        >
          {copy.speakHint}
        </p>

        {/* The second way in. Under the microphone rather than beside it: the
            mic stays the thing you reach for first, because it asks least of
            someone who cannot comfortably type. Both land on the same
            transcript, so neither path is a lesser version of the other. */}
        <form
          onSubmit={(event) => {
            event.preventDefault();
            void submitTyped();
          }}
          className="flex w-full max-w-[420px] flex-col items-center gap-3"
        >
          <span className="text-xs" style={{ color: "var(--ink-45)" }} lang={language}>
            {copy.orType}
          </span>

          <div className="flex w-full gap-2 max-[400px]:flex-col">
            <input
              value={typed}
              onChange={(event) => setTyped(event.target.value)}
              placeholder={copy.typePlaceholder}
              disabled={sending}
              aria-label={copy.typePlaceholder}
              lang={language}
              className="min-w-0 flex-1 rounded-full px-4.5 py-2.5 text-[15px] disabled:opacity-50"
              style={{
                background: "var(--color-surface)",
                border: "1px solid var(--ink-22)",
                padding: "0.625rem 1.125rem",
              }}
            />
            <button
              type="submit"
              disabled={sending || typed.trim() === ""}
              className="vp-pill vp-pill-primary flex-none justify-center disabled:opacity-40"
              lang={language}
            >
              {sending ? copy.loading : copy.typeSubmit}
            </button>
          </div>

          {error && (
            <p className="text-center text-[13px]" style={{ color: "var(--color-danger)" }}>
              {error}
            </p>
          )}
        </form>

        <PrivacyNote />
      </div>
      </section>

      {/* What this is, in the space the hero leaves on a tall screen.
      
          Deliberately quiet. The microphone is where this page spends its
          boldness, and a second loud thing would compete with the one action
          anybody needs to take. Hairline rule, body type, no cards.
      
          Numbered because it is genuinely a sequence -- speak, check, see --
          and someone who reads slowly is told the order rather than left to
          infer it from position. */}
      <section
        className="border-t px-[7vw] py-[clamp(2.5rem,5vw,4rem)]"
        style={{ borderColor: "var(--ink-09)" }}
        aria-labelledby="about-voicepath"
      >
        <h2
          id="about-voicepath"
          className="font-display text-[clamp(1.25rem,2vw,1.6rem)] tracking-[-0.02em]"
          lang={language}
        >
          {copy.aboutTitle}
        </h2>

        <ol className="mt-7 grid gap-x-10 gap-y-7 lg:grid-cols-3">
          {copy.aboutSteps.map((step, index) => (
            <li key={step.title} className="flex gap-4">
              <span
                className="font-mono flex-none pt-[3px] text-[12px] tabular-nums"
                style={{ color: "var(--ink-38)" }}
                aria-hidden
              >
                {index + 1}
              </span>
              <div className="min-w-0">
                <p
                  className="font-display text-[16.5px] leading-snug tracking-[-0.015em]"
                  lang={language}
                >
                  {step.title}
                </p>
                <p
                  className="mt-1.5 max-w-[34em] text-[14.5px] leading-relaxed"
                  style={{ color: "var(--ink-62)" }}
                  lang={language}
                >
                  {step.body}
                </p>
              </div>
            </li>
          ))}
        </ol>

        {/* The most useful sentence on the page for someone who has dealt with
            a government portal before. */}
        <p
          className="mt-8 max-w-[44em] border-t pt-6 text-[14px] leading-relaxed"
          style={{ borderColor: "var(--ink-06)", color: "var(--ink-55)" }}
          lang={language}
        >
          {copy.aboutNote}
        </p>
      </section>
    </div>
  );
}
