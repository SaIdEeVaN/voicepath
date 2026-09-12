"use client";

/**
 * About VoicePath.
 *
 * Everything here is true of the product and checkable against it: how a score
 * is arrived at, what the system refuses to assert, what happens to a
 * recording. It makes no claim about who built it, because a page that
 * invented a team would be the one kind of fiction this codebase exists to
 * refuse -- the same rule that stops an explanation claiming a skill nobody
 * mentioned.
 *
 * Written in all three languages rather than translated into them, like the
 * rest of `i18n.ts`.
 */

import Link from "next/link";

import { copyFor } from "@/lib/i18n";
import { useSession } from "@/lib/session";

export default function AboutPage() {
  const { language } = useSession();
  const copy = copyFor(language);

  return (
    <section className="mx-auto w-full max-w-[760px] flex-1 px-[7vw] py-[clamp(2.5rem,6vw,4.5rem)] pb-20">
      <h1
        className="vp-display text-[clamp(1.875rem,3.6vw,2.75rem)]"
        lang={language}
      >
        {copy.aboutPageTitle}
      </h1>

      <p
        className="mt-5 max-w-[32em] text-[17px] leading-relaxed"
        style={{ color: "var(--ink-70)" }}
        lang={language}
      >
        {copy.aboutPageLede}
      </p>

      {/* Hairline-separated rather than carded. The same reasoning as the
          landing page: this is reading, and boxes around prose add weight
          without adding meaning. */}
      <div className="mt-12 flex flex-col">
        {copy.aboutPageSections.map((section) => (
          <div
            key={section.heading}
            className="border-t py-7"
            style={{ borderColor: "var(--ink-09)" }}
          >
            <h2
              className="font-display text-[19px] leading-snug tracking-[-0.02em]"
              lang={language}
            >
              {section.heading}
            </h2>
            <p
              className="mt-2.5 max-w-[40em] text-[15px] leading-relaxed"
              style={{ color: "var(--ink-62)" }}
              lang={language}
            >
              {section.body}
            </p>
          </div>
        ))}
      </div>

      <div className="mt-10">
        <Link href="/speak" className="vp-pill vp-pill-primary" lang={language}>
          {copy.speakHint}
        </Link>
      </div>
    </section>
  );
}
