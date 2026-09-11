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
import Link from "next/link";
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
    <section className="grid flex-1 items-center gap-16 px-[7vw] py-[clamp(2.5rem,6vw,4.5rem)] lg:grid-cols-[minmax(0,1.15fr)_minmax(0,0.85fr)]">
      <div>
        <h1 className="vp-statement max-w-[13em]" lang={language}>
          {copy.statement}
        </h1>

        {/* The same promise in the other two languages. Pressing one switches
            and starts, so a wrong default costs one tap, not a hunt. */}
        <div className="mt-9 flex max-w-[520px] flex-col gap-0.5">
          {others.map((entry) => (
            <button
              key={entry.code}
              type="button"
              onClick={() => start(entry.code)}
              className="flex items-baseline gap-3.5 border-t py-3 text-left transition-opacity hover:opacity-60"
              style={{ borderColor: "var(--ink-09)" }}
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
        <button
          type="button"
          onClick={() => start(language)}
          className="relative grid h-[196px] w-[196px] place-items-center rounded-full transition-transform hover:-translate-y-0.5"
          style={{
            background: "var(--color-accent)",
            color: "var(--color-paper)",
            boxShadow:
              "0 18px 44px -20px color-mix(in srgb, var(--color-accent) 65%, transparent)",
          }}
        >
          {/* The breath is the one ambient motion in the product: it says the
              screen is ready to listen before anyone has spoken. */}
          <span
            className="vp-breathe pointer-events-none absolute -inset-1.5 rounded-full border"
            style={{ borderColor: "var(--color-accent)" }}
          />
          <MicIcon size={52} />
          <span className="sr-only">{copy.speakHint}</span>
        </button>

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

        {/* Quiet on purpose. The hero belongs to the person who came here to
            speak; an operator knows what they are looking for. The route is
            token-gated server-side either way, so this is a signpost and not
            a door. */}
        <Link
          href="/admin"
          className="text-xs underline-offset-4 hover:underline"
          style={{ color: "var(--ink-38)" }}
        >
          Admin dashboard
        </Link>
      </div>
    </section>
  );
}
