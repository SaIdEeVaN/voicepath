"use client";

import { AdminTable, type Column } from "@/components/AdminTable";
import { useAdminToken } from "@/lib/admin-token";
import type { SkillCandidate } from "@/lib/types";

const columns: Column<SkillCandidate>[] = [
  { key: "code", label: "Code", width: "minmax(0,0.6fr)", render: (r) => r.code, mono: true },
  { key: "name", label: "Skill", width: "minmax(0,2fr)", render: (r) => r.name },
  {
    key: "category",
    label: "Category",
    width: "minmax(0,1fr)",
    render: (r) => r.category,
    dim: true,
  },
  {
    key: "hint",
    label: "Plain-language hint",
    width: "minmax(0,2.4fr)",
    render: (r) => r.hint ?? "—",
    dim: true,
  },
];

export default function AdminTaxonomyPage() {
  const [token] = useAdminToken();
  return (
    <AdminTable
      endpoint="/api/admin/taxonomy"
      token={token}
      columns={columns}
      emptyMessage="The taxonomy is empty."
    />
  );
}
