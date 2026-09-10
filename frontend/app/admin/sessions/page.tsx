"use client";

/**
 * Read-only QA view (PRD section 5).
 *
 * Shows whether matching and explanation are behaving. Deliberately carries no
 * transcript column: QA needs to see the machine's output, not what people
 * said about their lives.
 */

import { AdminTable, type Column } from "@/components/AdminTable";
import { useAdminToken } from "@/lib/admin-token";

interface AuditRow {
  id: string;
  created_at: string;
  language_detected: string | null;
  audio_retained: boolean;
  match_count: number;
  question_count: number;
  best_score: number | null;
}

const columns: Column<AuditRow>[] = [
  {
    key: "created",
    label: "When",
    width: "minmax(0,1.2fr)",
    render: (r) => new Date(r.created_at).toLocaleString(),
    dim: true,
  },
  {
    key: "lang",
    label: "Language",
    width: "minmax(0,0.6fr)",
    render: (r) => r.language_detected ?? "—",
    mono: true,
  },
  {
    key: "matches",
    label: "Matches",
    width: "minmax(0,0.6fr)",
    render: (r) => String(r.match_count),
    mono: true,
  },
  {
    key: "questions",
    label: "Questions",
    width: "minmax(0,0.6fr)",
    render: (r) => String(r.question_count),
    mono: true,
  },
  {
    key: "best",
    label: "Best match",
    width: "minmax(0,0.7fr)",
    render: (r) => (r.best_score === null ? "—" : `${Math.round(r.best_score * 100)}%`),
    mono: true,
  },
  {
    key: "audio",
    label: "Audio kept",
    width: "minmax(0,0.7fr)",
    render: (r) => (r.audio_retained ? "yes" : "no"),
    dim: true,
  },
];

export default function AdminSessionsPage() {
  const [token] = useAdminToken();
  return (
    <AdminTable
      endpoint="/api/admin/sessions"
      token={token}
      columns={columns}
      emptyMessage="No sessions recorded yet."
    />
  );
}
