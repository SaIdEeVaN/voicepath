"use client";

/**
 * Standing notices.
 *
 * `PrivacyNote` states the data-minimisation promise in the person's own
 * language, in plain words rather than legal boilerplate -- PRD section 7 asks
 * for exactly that, on the surface, not in a policy page.
 *
 * `DegradedNote` is the counterpart: when the language services are not
 * configured the interface says so, rather than presenting a thinner result as
 * though it were the full one.
 */

import { copyFor } from "@/lib/i18n";
import { useDegraded, useSession } from "@/lib/session";

export function PrivacyNote({ className = "" }: { className?: string }) {
  const { language } = useSession();
  const copy = copyFor(language);

  return (
    <p
      className={`flex max-w-[26em] items-start gap-2 rounded-full px-3.5 py-2 text-xs leading-snug ${className}`}
      style={{ background: "var(--ink-04)", color: "var(--ink-62)" }}
      lang={language}
    >
      <span
        className="mt-1.5 h-1.5 w-1.5 flex-none rounded-full"
        style={{ background: "var(--color-accent-alt)" }}
      />
      {copy.notKept}
    </p>
  );
}

export function DegradedNote() {
  const { language } = useSession();
  const { language: languageOffline } = useDegraded();
  if (!languageOffline) return null;

  return (
    <div
      className="mx-auto mb-8 flex max-w-[46em] items-start gap-3 rounded-xl px-4 py-3 text-sm leading-relaxed"
      style={{
        background: "color-mix(in srgb, var(--color-caution) 14%, transparent)",
        color: "var(--color-caution-ink)",
      }}
      role="status"
      lang={language}
    >
      <span
        className="mt-1.5 h-2 w-2 flex-none rotate-45"
        style={{ background: "var(--color-caution-mark)" }}
      />
      {copyFor(language).offlineNotice}
    </div>
  );
}

export function ErrorNote({ message }: { message: string }) {
  return (
    <div
      className="flex items-start gap-3 rounded-xl px-4 py-3 text-sm leading-relaxed"
      style={{
        background: "color-mix(in srgb, var(--color-danger) 10%, transparent)",
        color: "var(--color-danger)",
      }}
      role="alert"
    >
      <span
        className="mt-1.5 h-2 w-2 flex-none rotate-45"
        style={{ background: "var(--color-danger)" }}
      />
      {message}
    </div>
  );
}
