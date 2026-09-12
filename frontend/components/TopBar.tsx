"use client";

/**
 * Minimal chrome (PRD section 2: the large voice control is the primary
 * interaction, not a nav bar).
 *
 * So this carries the wordmark, three quiet links and the language switch.
 * The flow still moves forward on its own; these are ways out of it rather
 * than a menu to navigate by.
 *
 * Home exists even though the wordmark already goes there, because a wordmark
 * reads as a logo and only some people know it is also a button. Admin is a
 * signpost, not a door -- the route is token-gated server-side either way.
 *
 * The links sit in the middle of the bar, held there by a three-column grid
 * with equal outer columns -- so the centre is the centre of the header rather
 * than of whatever space is left over, and it does not shift when the language
 * switch changes width between scripts.
 *
 * On a phone that grid collapses to two rows: wordmark and language switch on
 * the first, links centred underneath. Fitting all of it on one line at 360px
 * would mean type too small to tap accurately, and a header that scrolls
 * sideways is worse than one that takes two lines.
 */

import Link from "next/link";
import { usePathname } from "next/navigation";

import { LANGUAGES, copyFor } from "@/lib/i18n";
import { useSession } from "@/lib/session";
import type { Language } from "@/lib/types";

export function TopBar() {
  const pathname = usePathname();
  const { language, setLanguage } = useSession();
  const copy = copyFor(language);

  // The admin surface is a different product for a different person.
  if (pathname?.startsWith("/admin")) return null;

  return (
    <header
      className="sticky top-0 z-20 grid grid-cols-[1fr_auto_1fr] items-center gap-x-4 gap-y-2.5 border-b px-6 py-3 backdrop-blur max-[560px]:grid-cols-[auto_1fr] max-[560px]:px-4"
      style={{
        borderColor: "var(--ink-09)",
        background: "rgb(var(--paper-rgb) / 0.86)",
      }}
    >
      <Link
        href="/"
        className="font-display justify-self-start text-[16px] font-semibold tracking-[-0.02em]"
      >
        voicepath
      </Link>

      {/* Second row on a phone, spanning both columns there. */}
      <nav className="flex items-center justify-center gap-7 max-[560px]:order-3 max-[560px]:col-span-2 max-[560px]:gap-8">
        {[
          { href: "/", label: copy.navHome },
          { href: "/about", label: copy.navAbout },
          { href: "/admin", label: "Admin" },
        ].map((item) => {
          const active = pathname === item.href;
          return (
            <Link
              key={item.href}
              href={item.href}
              aria-current={active ? "page" : undefined}
              className="flex-none py-0.5 text-[15px] underline-offset-4 transition-colors hover:underline"
              style={{ color: active ? "var(--color-ink)" : "var(--ink-45)" }}
              lang={language}
            >
              {item.label}
            </Link>
          );
        })}
      </nav>

      <div
        className="flex flex-none justify-self-end gap-1 rounded-full p-[3px]"
        style={{ background: "var(--ink-04)" }}
        role="group"
        aria-label="Language"
      >
        {LANGUAGES.map((entry) => {
          const active = entry.code === language;
          return (
            <button
              key={entry.code}
              type="button"
              onClick={() => setLanguage(entry.code as Language)}
              aria-pressed={active}
              lang={entry.code}
              className="rounded-full px-3.5 py-1.5 text-[13px] font-medium transition-colors"
              style={{
                background: active ? "var(--color-surface)" : "transparent",
                color: active ? "var(--color-ink)" : "var(--ink-55)",
                boxShadow: active ? "0 1px 3px rgb(var(--ink-rgb) / 0.12)" : "none",
              }}
            >
              {entry.native}
            </button>
          );
        })}
      </div>
    </header>
  );
}
