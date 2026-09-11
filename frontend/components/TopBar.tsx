"use client";

/**
 * Minimal chrome (PRD section 2: the large voice control is the primary
 * interaction, not a nav bar).
 *
 * So this carries the wordmark, the language switch, and one link to admin.
 * There is no other navigation -- the flow moves forward on its own, and every
 * screen that needs a way back provides its own.
 *
 * Admin sits here because an operator should not have to scroll the landing
 * page to reach their own tool. It stays visually quiet: the hero belongs to
 * the person who came to speak, and the route is token-gated server-side, so
 * this is a signpost rather than a door.
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
      className="sticky top-0 z-20 flex items-center gap-6 border-b px-6 py-2.5 backdrop-blur max-[420px]:gap-3 max-[420px]:px-4"
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

      <Link
        href="/admin"
        className="flex-none text-xs underline-offset-4 transition-colors hover:underline"
        style={{ color: "var(--ink-45)" }}
      >
        Admin
      </Link>

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
