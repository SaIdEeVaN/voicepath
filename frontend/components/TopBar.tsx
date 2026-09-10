"use client";

/**
 * Minimal chrome (PRD section 2: the large voice control is the primary
 * interaction, not a nav bar).
 *
 * So this carries only the wordmark and the language switch. There is no
 * navigation here -- the flow moves forward on its own, and every screen that
 * needs a way back provides its own.
 */

import Link from "next/link";
import { usePathname } from "next/navigation";

import { LANGUAGES } from "@/lib/i18n";
import { useSession } from "@/lib/session";
import type { Language } from "@/lib/types";

export function TopBar() {
  const pathname = usePathname();
  const { language, setLanguage } = useSession();

  // The admin surface is a different product for a different person.
  if (pathname?.startsWith("/admin")) return null;

  return (
    <header
      className="sticky top-0 z-20 flex items-center gap-6 border-b px-6 py-2.5 backdrop-blur"
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

      <div className="flex-1" />

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
