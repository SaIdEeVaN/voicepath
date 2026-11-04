"use client";

/**
 * Sources: what the assistant is allowed to answer from.
 *
 * Every page the web search fetches lands here as pending, and nothing is said
 * from it until someone approves it. That gate exists because the old rule --
 * any .gov.in page is trusted at once -- stored football match reports, exam
 * syllabi and a search-engine-optimisation guide as scheme guidance, and the
 * assistant cited them.
 *
 * Rejecting is reversible (approve it again here), and a rejected page stays
 * rejected even if a later search fetches it again.
 */

import { useCallback, useEffect, useState } from "react";

import { API_BASE } from "@/lib/api";
import { useAdminToken } from "@/lib/admin-token";

interface Source {
  id: number;
  title: string;
  source: string;
  source_url: string | null;
  source_domain: string | null;
  trust_tier: number;
  status: "active" | "pending_verification" | "rejected" | "archived";
  retrieved_at: string | null;
  chunks: number;
  excerpt: string | null;
}

const FILTERS = [
  { value: "pending_verification", label: "Waiting for review" },
  { value: "active", label: "Answerable" },
  { value: "rejected", label: "Rejected" },
  { value: "", label: "All" },
] as const;

const STATUS_LABEL: Record<Source["status"], string> = {
  active: "Answerable",
  pending_verification: "Waiting",
  rejected: "Rejected",
  archived: "Archived",
};

export default function AdminSourcesPage() {
  const [token] = useAdminToken();
  const [filter, setFilter] = useState<string>("pending_verification");
  const [rows, setRows] = useState<Source[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<number | null>(null);

  const load = useCallback(async () => {
    if (!token) {
      setRows([]);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const query = filter ? `?status=${encodeURIComponent(filter)}` : "";
      const response = await fetch(`${API_BASE}/api/admin/sources${query}`, {
        headers: { Authorization: `Bearer ${token}` },
        cache: "no-store",
      });
      if (!response.ok) {
        const body = (await response.json().catch(() => ({}))) as { detail?: string };
        throw new Error(body.detail ?? `Request failed (${response.status})`);
      }
      setRows((await response.json()) as Source[]);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Request failed.");
      setRows([]);
    } finally {
      setLoading(false);
    }
  }, [token, filter]);

  useEffect(() => {
    void load();
  }, [load]);

  const decide = useCallback(
    async (id: number, action: "verify" | "reject") => {
      setBusy(id);
      setError(null);
      try {
        const response = await fetch(`${API_BASE}/api/admin/sources/${id}/${action}`, {
          method: "POST",
          headers: { Authorization: `Bearer ${token}` },
        });
        if (!response.ok) {
          const body = (await response.json().catch(() => ({}))) as { detail?: string };
          throw new Error(body.detail ?? `Request failed (${response.status})`);
        }
        await load();
      } catch (cause) {
        setError(cause instanceof Error ? cause.message : "Request failed.");
      } finally {
        setBusy(null);
      }
    },
    [token, load],
  );

  if (!token) {
    return (
      <p className="text-sm" style={{ color: "var(--ink-55)" }}>
        Enter an admin token to review sources.
      </p>
    );
  }

  return (
    <div className="flex flex-col gap-5">
      <p className="max-w-[46em] text-[13.5px] leading-relaxed" style={{ color: "var(--ink-62)" }}>
        The assistant answers scheme questions only from <strong>answerable</strong> sources.
        Pages found by web search wait here until someone approves them. Approve a page only
        if it describes a scheme&apos;s rules, benefits or how to apply; a news report or a
        menu page is not guidance, whatever its domain.
      </p>

      <div className="flex flex-wrap gap-2" role="group" aria-label="Filter sources">
        {FILTERS.map((option) => (
          <button
            key={option.value || "all"}
            type="button"
            aria-pressed={filter === option.value}
            onClick={() => setFilter(option.value)}
            className="vp-chip"
            data-on={filter === option.value}
          >
            {option.label}
          </button>
        ))}
      </div>

      {error && (
        <p className="text-sm" style={{ color: "var(--color-danger)" }} role="alert">
          {error}
        </p>
      )}
      {loading && (
        <p className="text-sm" style={{ color: "var(--ink-55)" }}>
          Loading…
        </p>
      )}
      {!loading && !error && rows.length === 0 && (
        <p className="text-sm" style={{ color: "var(--ink-55)" }}>
          {filter === "pending_verification"
            ? "Nothing is waiting for review."
            : "No sources here."}
        </p>
      )}

      <ul className="flex flex-col gap-3">
        {rows.map((row) => {
          const link = row.source_url ?? (row.source.startsWith("http") ? row.source : null);
          return (
            <li
              key={row.id}
              className="rounded-[14px] p-5"
              style={{ background: "var(--color-surface)", border: "1px solid var(--ink-12)" }}
            >
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0 flex-1">
                  <p className="font-display text-[16px] leading-snug tracking-[-0.01em]">
                    {row.title}
                  </p>
                  <p className="font-mono mt-1 text-[11.5px]" style={{ color: "var(--ink-45)" }}>
                    {[
                      row.source_domain ?? "uploaded document",
                      `tier ${row.trust_tier}`,
                      `${row.chunks} passages`,
                      row.retrieved_at ? new Date(row.retrieved_at).toLocaleDateString() : null,
                    ]
                      .filter(Boolean)
                      .join(" · ")}
                  </p>
                </div>
                <span
                  className="font-mono rounded px-2 py-1 text-[11px]"
                  style={{
                    background: "var(--ink-04)",
                    color:
                      row.status === "active"
                        ? "var(--color-accent-deep)"
                        : row.status === "rejected"
                          ? "var(--color-danger)"
                          : "var(--color-caution-ink)",
                  }}
                >
                  {STATUS_LABEL[row.status]}
                </span>
              </div>

              {row.excerpt && (
                <p className="mt-3 text-[13px] leading-relaxed" style={{ color: "var(--ink-70)" }}>
                  {row.excerpt}…
                </p>
              )}

              <div className="mt-4 flex flex-wrap items-center gap-3">
                {row.status !== "active" && (
                  <button
                    type="button"
                    disabled={busy === row.id}
                    onClick={() => void decide(row.id, "verify")}
                    className="vp-pill vp-pill-primary !px-4 !py-2 text-[13px]"
                  >
                    Approve
                  </button>
                )}
                {row.status !== "rejected" && (
                  <button
                    type="button"
                    disabled={busy === row.id}
                    onClick={() => void decide(row.id, "reject")}
                    className="vp-pill vp-pill-quiet !px-4 !py-2 text-[13px]"
                  >
                    Reject
                  </button>
                )}
                {link && (
                  <a
                    href={link}
                    target="_blank"
                    rel="noreferrer noopener"
                    className="text-[13px] underline underline-offset-4"
                    style={{ color: "var(--ink-62)" }}
                  >
                    Open the page
                  </a>
                )}
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
