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
 *
 * Laid out two columns wide on a desktop and one on a phone. A single column
 * at this length is a very tall page on a monitor, and two is as far as it can
 * widen before the measure drops under about forty characters a line, which is
 * where prose stops being comfortable to read.
 */

import Link from "next/link";

import { copyFor } from "@/lib/i18n";
import { useSession } from "@/lib/session";

export default function AboutPage() {
  const { language } = useSession();
  const copy = copyFor(language);

  return (
    <section className="mx-auto w-full max-w-[1080px] flex-1 px-[7vw] py-[clamp(2.5rem,6vw,4.5rem)] pb-20">
      {/* Title and lede sit side by side on a wide screen rather than stacked,
          which is where most of the page's height was going. */}
      <header className="grid gap-x-14 gap-y-5 lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)] lg:items-end">
        <h1
          className="vp-display text-[clamp(1.875rem,3.6vw,2.75rem)]"
          lang={language}
        >
          {copy.aboutPageTitle}
        </h1>

        <p
          className="max-w-[34em] text-[17px] leading-relaxed"
          style={{ color: "var(--ink-70)" }}
          lang={language}
        >
          {copy.aboutPageLede}
        </p>
      </header>

      {/* Two columns, not more, and not before 1024px.
      
          Measured across the widths that matter: at 1440 and 1280 each column
          runs about 68 characters a line, at 1024 about 55 -- both inside the
          range prose stays comfortable in. At 768, which is where `md` would
          have split it, the measure falls to about 40, which is where reading
          starts to feel like a newspaper column. So it splits at `lg` and
          stays a single column below that.
      
          A third column would put every width under forty. */}
      <div className="mt-14 grid gap-x-14 gap-y-0 lg:grid-cols-2">
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
              className="mt-2.5 text-[15px] leading-relaxed"
              style={{ color: "var(--ink-62)" }}
              lang={language}
            >
              {section.body}
            </p>
          </div>
        ))}
      </div>

      <div
        className="mt-10 border-t pt-9"
        style={{ borderColor: "var(--ink-09)" }}
      >
        <Link href="/speak" className="vp-pill vp-pill-primary" lang={language}>
          {copy.speakHint}
        </Link>
      </div>
    </section>
  );
}
