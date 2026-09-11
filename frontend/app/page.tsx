"use client";

/**
 * Landing (PRD section 5).
 *
 * The hero is the statement and the microphone, nothing else. The other two
 * languages sit underneath as their own sentences rather than as a dropdown,
 * so a person who cannot read the language currently showing can still see
 * their own and press it.
 */

import Link from "next/link";
import { useRouter } from "next/navigation";

import { MicIcon } from "@/components/MicIcon";
import { PrivacyNote } from "@/components/Notices";
import { COPY, LANGUAGES, copyFor } from "@/lib/i18n";
import { useSession } from "@/lib/session";
import type { Language } from "@/lib/types";

export default function LandingPage() {
  const router = useRouter();
  const { language, setLanguage } = useSession();
  const copy = copyFor(language);

  const others = LANGUAGES.filter((entry) => entry.code !== language);

  const start = (chosen: Language) => {
    setLanguage(chosen);
    router.push("/speak");
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
