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
 * It wraps rather than overflows. On a 360px phone the wordmark, three links
 * and the language switch do not fit on one line, and a header that scrolls
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
      className="sticky top-0 z-20 flex flex-wrap items-center gap-x-5 gap-y-2 border-b px-6 py-2.5 backdrop-blur max-[460px]:gap-x-3.5 max-[460px]:px-4"
      style={{
        borderColor: "var(--ink-09)",
        background: "rgb(var(--paper-rgb) / 0.86)",
      }}
    >
      <Link
        href="/"
        className="font-display flex-none text-[15px] font-semibold tracking-[-0.02em]"
      >
        voicepath
      </Link>

      <nav className="flex flex-1 items-center gap-5 max-[460px]:gap-3.5">
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
              className="flex-none text-[13px] underline-offset-4 transition-colors hover:underline max-[460px]:text-xs"
              style={{ color: active ? "var(--color-ink)" : "var(--ink-45)" }}
              lang={language}
            >
              {item.label}
            </Link>
          );
        })}
      </nav>

      <div
        className="flex flex-none gap-1 rounded-full p-[3px]"
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
              className="rounded-full px-3 py-1 text-xs font-medium transition-colors"
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
