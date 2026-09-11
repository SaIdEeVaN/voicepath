"use client";

/**
 * The admin data table.
 *
 * One component for all three admin views -- they differ only in columns and
 * endpoint, and three near-identical tables would drift apart within a month.
 */

import { useCallback, useEffect, useState } from "react";

import { API_BASE } from "@/lib/api";

export interface Column<T> {
  key: string;
  label: string;
  width: string;
  render(row: T): string;
  mono?: boolean;
  dim?: boolean;
}

export function AdminTable<T>({
  endpoint,
  token,
  columns,
  emptyMessage = "Nothing here yet.",
}: {
  endpoint: string;
  token: string;
  columns: Column<T>[];
  emptyMessage?: string;
}) {
  const [rows, setRows] = useState<T[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    if (!token) {
      setRows([]);
      setError(null);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(`${API_BASE}${endpoint}`, {
        headers: { Authorization: `Bearer ${token}` },
        cache: "no-store",
      });
      if (!response.ok) {
        const body = (await response.json().catch(() => ({}))) as {
          detail?: string;
        };
        throw new Error(body.detail ?? `Request failed (${response.status})`);
      }
      setRows((await response.json()) as T[]);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Request failed.");
      setRows([]);
    } finally {
      setLoading(false);
    }
  }, [endpoint, token]);

  useEffect(() => {
    void load();
  }, [load]);

  const template = columns.map((column) => column.width).join(" ");

  if (!token) {
    return (
      <p className="text-sm" style={{ color: "var(--ink-55)" }}>
        Enter an admin token to load this table.
      </p>
    );
  }

  return (
    <div
      className="overflow-x-auto rounded-[14px]"
      style={{
        border: "1px solid var(--ink-12)",
        background: "var(--color-surface)",
      }}
    >
      {/* A minimum width the columns can actually hold, so narrow screens
          scroll the table rather than crushing six columns into 310px. The
          wrapper scrolls; the page itself never does. */}
      <div className="min-w-[760px]">
      <div
        className="font-mono grid gap-5 px-6 py-3.5 text-[10.5px] tracking-[0.08em]"
        style={{
          gridTemplateColumns: template,
          background: "var(--ink-04)",
          color: "var(--ink-45)",
        }}
      >
        {columns.map((column) => (
          <div key={column.key}>{column.label.toUpperCase()}</div>
        ))}
      </div>

      {loading && (
        <p className="px-6 py-5 text-sm" style={{ color: "var(--ink-55)" }}>
          Loading…
        </p>
      )}

      {error && (
        <p className="px-6 py-5 text-sm" style={{ color: "var(--color-danger)" }}>
          {error}
        </p>
      )}

      {!loading && !error && rows.length === 0 && (
        <p className="px-6 py-5 text-sm" style={{ color: "var(--ink-55)" }}>
          {emptyMessage}
        </p>
      )}

      {rows.map((row, index) => (
        <div
          key={index}
          className="grid items-center gap-5 border-t px-6 py-4 text-[13.5px]"
          style={{ gridTemplateColumns: template, borderColor: "var(--ink-06)" }}
        >
          {columns.map((column) => (
            <div
              key={column.key}
              className={`min-w-0 truncate ${column.mono ? "font-mono text-xs" : ""}`}
              style={column.dim ? { color: "var(--ink-55)" } : undefined}
              title={column.render(row)}
            >
              {column.render(row)}
            </div>
          ))}
        </div>
      ))}
      </div>
    </div>
  );
}
