"use client";

import { AdminTable, type Column } from "@/components/AdminTable";
import { useAdminToken } from "@/lib/admin-token";
import type { OpportunityDetail } from "@/lib/types";

const columns: Column<OpportunityDetail>[] = [
  { key: "title", label: "Title", width: "minmax(0,2fr)", render: (r) => r.title },
  {
    key: "org",
    label: "Organisation",
    width: "minmax(0,1.4fr)",
    render: (r) => r.organization,
    dim: true,
  },
  {
    key: "location",
    label: "Location",
    width: "minmax(0,1fr)",
    render: (r) => r.location,
    dim: true,
  },
  { key: "type", label: "Type", width: "minmax(0,1fr)", render: (r) => r.type, dim: true },
  {
    key: "skills",
    label: "Required skills",
    width: "minmax(0,1.4fr)",
    render: (r) => r.required_skills.map((s) => s.code).join(", ") || "—",
    mono: true,
  },
  {
    key: "source",
    label: "Source",
    width: "minmax(0,1.6fr)",
    render: (r) => r.source_reference ?? "—",
    mono: true,
    dim: true,
  },
];

export default function AdminOpportunitiesPage() {
  const [token] = useAdminToken();
  return (
    <AdminTable
      endpoint="/api/admin/opportunities"
      token={token}
      columns={columns}
      emptyMessage="No active opportunities."
    />
  );
}
