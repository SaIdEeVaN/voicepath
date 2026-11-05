"use client";

/**
 * The page foot: quiet links for the people who need them, not a menu.
 *
 * Admin lives here since 2026-11-05 -- it is for the people running VoicePath,
 * and in the main menu it was a choice everyone else had to read past. The
 * route is token-gated on the server either way.
 */

import Link from "next/link";
import { usePathname } from "next/navigation";

import { copyFor } from "@/lib/i18n";
import { useSession } from "@/lib/session";

export function SiteFooter() {
  const pathname = usePathname();
  const { language } = useSession();
  const copy = copyFor(language);
  if (pathname?.startsWith("/admin")) return null;

  return (
    <footer
      className="mt-auto border-t px-[7vw] py-6 print:hidden"
      style={{ borderColor: "var(--ink-09)" }}
    >
      <div
        className="mx-auto flex max-w-[1180px] flex-wrap items-center gap-x-6 gap-y-2 text-[13px]"
        style={{ color: "var(--ink-55)" }}
        lang={language}
      >
        <span className="font-display tracking-[-0.01em]" style={{ color: "var(--ink-70)" }}>
          voicepath
        </span>
        <Link href="/about" className="py-2 underline-offset-4 hover:underline">
          {copy.navAbout}
        </Link>
        <Link href="/admin" className="py-2 underline-offset-4 hover:underline">
          {copy.footerAdmin}
        </Link>
      </div>
    </footer>
  );
}
