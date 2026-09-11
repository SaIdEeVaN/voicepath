"use client";

/**
 * The numbers behind the dashboard (PRD section 18).
 *
 * `/admin` was three navigation cards and no figures, so the one question an
 * operator actually arrives with -- is anything happening? -- had no answer on
 * the page.
 *
 * Deliberately plain, like the rest of admin: this is a different product for
 * a different person, and dressing it like the beneficiary surface would blur
 * a line the PRD draws sharply. Numbers first, no chrome around them.
 *
 * Nothing here is a transcript or a question. Popular skills are taxonomy
 * names, not the words someone used about their own life -- the same rule
 * `/admin/sessions` follows, applied one level up.
 */

import { useCallback, useEffect, useState } from "react";

import { API_BASE } from "@/lib/api";
import { useAdminToken } from "@/lib/admin-token";

interface Counted {
  count: number;
}
interface TypeCount extends Counted {
  type: string;
}
interface NamedCount extends Counted {
  name: string;
  code?: string | null;
}
interface LanguageCount extends Counted {
  language: string;
}

interface Overview {
  schemes: {
    total: number;
    active: number;
    inactive: number;
    by_type: TypeCount[];
  };
  sessions: {
    total: number;
    today: number;
    questions: number;
    questions_today: number;
    by_language: LanguageCount[];
  };
  corpus: { documents: number; chunks: number };
  popular: { skills: NamedCount[]; locations: NamedCount[] };
}

export function AdminOverview() {
  const [token] = useAdminToken();
  const [data, setData] = useState<Overview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    if (!token) {
      setData(null);
      setError(null);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(`${API_BASE}/api/admin/overview`, {
        headers: { Authorization: `Bearer ${token}` },
        cache: "no-store",
      });
      if (!response.ok) {
        const body = (await response.json().catch(() => ({}))) as {
          detail?: string;
        };
        // The backend's own words. It now distinguishes "wrong token" from
        // "this server has no admin configured", and that difference is the
        // whole point of showing it rather than a generic failure.
        throw new Error(body.detail ?? `Request failed (${response.status})`);
      }
      setData((await response.json()) as Overview);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Request failed.");
      setData(null);
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    void load();
  }, [load]);

  if (!token) {
    return (
      <p className="text-[13px]" style={{ color: "var(--ink-45)" }}>
        Enter the admin token above to see the figures.
      </p>
    );
  }

  if (error) {
    return (
      <p
        className="rounded-[10px] px-3.5 py-3 text-[13px] leading-relaxed"
        style={{
          color: "var(--color-danger)",
          background: "var(--ink-03)",
        }}
      >
        {error}
      </p>
    );
  }

  if (loading && !data) {
    return (
      <p className="text-[13px]" style={{ color: "var(--ink-45)" }}>
        Counting…
      </p>
    );
  }

  if (!data) return null;

  const { schemes, sessions, corpus, popular } = data;

  return (
    <div className="flex flex-col gap-5">
      <div className="grid gap-2.5 [grid-template-columns:repeat(auto-fit,minmax(150px,1fr))]">
        <Stat
          value={schemes.active}
          label="Active schemes"
          note={
            schemes.inactive > 0
              ? `${schemes.inactive} deactivated`
              : `${schemes.total} in total`
          }
        />
        <Stat
          value={sessions.total}
          label="Sessions"
          note={`${sessions.today} today`}
        />
        <Stat
          value={sessions.questions}
          label="Questions asked"
          note={`${sessions.questions_today} today`}
        />
        <Stat
          value={corpus.chunks}
          label="Indexed passages"
          note={`${corpus.documents} document${corpus.documents === 1 ? "" : "s"}`}
        />
      </div>

      <div className="grid gap-3.5 [grid-template-columns:repeat(auto-fit,minmax(230px,1fr))]">
        <Breakdown
          title="By type"
          rows={schemes.by_type.map((t) => ({ name: t.type, count: t.count }))}
          empty="No active schemes."
        />
        <Breakdown
          title="Most common skills"
          rows={popular.skills}
          empty="Nobody has been matched yet."
        />
        <Breakdown
          title="Most common places"
          rows={popular.locations}
          empty="No locations recorded yet."
        />
        <Breakdown
          title="Languages"
          rows={sessions.by_language.map((l) => ({
            name: l.language,
            count: l.count,
          }))}
          empty="No sessions yet."
        />
      </div>
    </div>
  );
}

function Stat({
  value,
  label,
  note,
}: {
  value: number;
  label: string;
  note: string;
}) {
  return (
    <div
      className="rounded-[12px] px-4 py-3.5"
      style={{
        background: "var(--color-surface)",
        border: "1px solid var(--ink-09)",
      }}
    >
      <p className="font-display text-[28px] leading-none tracking-[-0.03em]">
        {value.toLocaleString("en-IN")}
      </p>
      <p className="mt-2 text-[13px]" style={{ color: "var(--ink-70)" }}>
        {label}
      </p>
      <p
        className="font-mono mt-1 text-[10.5px] tracking-[0.05em]"
        style={{ color: "var(--ink-38)" }}
      >
        {note}
      </p>
    </div>
  );
}

function Breakdown({
  title,
  rows,
  empty,
}: {
  title: string;
  rows: { name: string; count: number }[];
  empty: string;
}) {
  return (
    <div
      className="rounded-[12px] px-4 py-3.5"
      style={{
        background: "var(--color-surface)",
        border: "1px solid var(--ink-09)",
      }}
    >
      <p className="vp-label">{title.toUpperCase()}</p>
      {rows.length === 0 ? (
        <p className="mt-2.5 text-[13px]" style={{ color: "var(--ink-45)" }}>
          {empty}
        </p>
      ) : (
        <ul className="mt-2.5 flex flex-col gap-1.5">
          {rows.slice(0, 5).map((row) => (
            <li
              key={row.name}
              className="flex items-baseline justify-between gap-3 text-[13.5px]"
            >
              <span className="min-w-0 truncate" style={{ color: "var(--ink-80)" }}>
                {row.name}
              </span>
              <span
                className="font-mono flex-none text-[12px]"
                style={{ color: "var(--ink-55)" }}
              >
                {row.count}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
