"use client";

/**
 * Admin shell (PRD section 5, Phase 2).
 *
 * Data management only. Deliberately plain: this is a different product for a
 * different person, and dressing it like the beneficiary-facing surface would
 * blur a line the PRD draws sharply.
 *
 * The token lives in sessionStorage and is sent as a bearer header. It is not
 * a security boundary -- every /api/admin/* route re-checks the role
 * server-side (section 6.6). This UI just avoids showing an empty table to
 * someone who has not authenticated.
 */

import type { ReactNode } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { useAdminToken } from "@/lib/admin-token";

const TABS = [
  { href: "/admin/opportunities", label: "Opportunities" },
  { href: "/admin/taxonomy", label: "Skill taxonomy" },
  { href: "/admin/sessions", label: "Sessions" },
];

export default function AdminLayout({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const [token, setToken] = useAdminToken();

  return (
    <div className="mx-auto w-full max-w-[1180px] px-[7vw] py-10 pb-20">
      <header className="flex flex-wrap items-end justify-between gap-7">
        <div>
          <p className="vp-label">PHASE 2 · ROLE-GATED</p>
          <h1 className="font-display mt-2.5 text-[34px] leading-tight tracking-[-0.03em]">
            Opportunity data
          </h1>
        </div>

        <div className="flex items-center gap-2">
          <div
            className="flex gap-1 rounded-lg p-1"
            style={{ background: "var(--ink-04)" }}
          >
            {TABS.map((tab) => {
              const active = pathname === tab.href;
              return (
                <Link
                  key={tab.href}
                  href={tab.href}
                  className="rounded-md px-3.5 py-1.5 text-[12.5px]"
                  style={{
                    background: active ? "var(--color-surface)" : "transparent",
                    boxShadow: active
                      ? "0 1px 3px rgb(var(--ink-rgb) / 0.12)"
                      : "none",
                  }}
                >
                  {tab.label}
                </Link>
              );
            })}
          </div>
        </div>
      </header>

      <label className="mt-7 flex max-w-[520px] flex-col gap-2">
        <span className="vp-label">ADMIN TOKEN</span>
        <input
          type="password"
          value={token}
          onChange={(event) => setToken(event.target.value)}
          placeholder="Bearer token"
          className="rounded-lg px-3.5 py-2.5 text-sm outline-none"
          style={{
            border: "1px solid var(--ink-12)",
            background: "var(--color-surface)",
          }}
        />
        <span className="text-xs" style={{ color: "var(--ink-45)" }}>
          Checked server-side on every request. Held for this tab only.
        </span>
      </label>

      <div className="mt-8">{children}</div>

      <p
        className="mt-4 max-w-[46em] text-xs leading-relaxed"
        style={{ color: "var(--ink-45)" }}
      >
        Admin is data management only — no beneficiary-facing surfaces. Every
        write goes through a server-side role check; sessions are read-only
        here, and transcripts are never shown.
      </p>
    </div>
  );
}
