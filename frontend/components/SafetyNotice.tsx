/**
 * Who to call, when someone has said they or a person near them is in danger.
 *
 * Shown in place of an answer, never beside one: a plea for help is not a
 * question about a scheme, and nothing else on the screen should compete
 * with it. Every number is a tel: link, because on the phones this is used on
 * a tap is a call, and the person may not be in a state to copy a number.
 *
 * The backend decides when this appears (app/services/safety.py), from fixed
 * patterns rather than a model, so it appears even when Groq is down.
 *
 * The server's answer says the same in a sentence, for reading aloud; the
 * screen shows the numbers instead, because someone in distress needs fewer
 * words, not more.
 *
 * The panel sets its own paper background and ink text, so it reads the same
 * on the dark assistant panel and on the light understanding screen.
 */

import { copyFor } from "@/lib/i18n";
import type { Copy } from "@/lib/i18n";
import type { Language } from "@/lib/types";

const OTHER_LINES: { number: string; label: keyof Copy }[] = [
  { number: "181", label: "safety181" },
  { number: "1098", label: "safety1098" },
  { number: "14416", label: "safety14416" },
];

export function SafetyNotice({ language }: { language: Language }) {
  const copy = copyFor(language);

  return (
    <div
      role="alert"
      className="flex flex-col gap-4 rounded-[14px] px-5 py-5"
      style={{
        background: "var(--color-paper)",
        color: "var(--color-ink)",
        borderLeft: "5px solid var(--color-danger)",
      }}
      lang={language}
    >
      <p className="text-[17px] font-semibold leading-snug">{copy.safetyTitle}</p>

      <a
        href="tel:112"
        className="flex items-center gap-4 self-start rounded-full px-6 py-3 no-underline"
        style={{ background: "var(--color-danger)", color: "var(--color-paper)" }}
      >
        <span className="font-display text-[30px] leading-none tracking-[-0.02em]">
          112
        </span>
        <span className="text-[14px] leading-tight">{copy.safety112}</span>
      </a>

      <ul className="flex flex-col gap-2">
        {OTHER_LINES.map((line) => (
          <li key={line.number}>
            <a
              href={`tel:${line.number}`}
              className="inline-flex items-baseline gap-3 underline-offset-4 hover:underline"
              style={{ color: "var(--color-ink)" }}
            >
              <span
                className="font-mono text-[17px] font-semibold"
                style={{ color: "var(--color-danger)" }}
              >
                {line.number}
              </span>
              <span className="text-[14px]">{copy[line.label] as string}</span>
            </a>
          </li>
        ))}
      </ul>

      <p className="text-[13.5px] leading-relaxed" style={{ color: "var(--ink-70)" }}>
        {copy.safetyCannotSend}
      </p>
    </div>
  );
}
