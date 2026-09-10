import { notFound } from "next/navigation";

import { OpportunityView } from "./OpportunityView";
import { API_BASE } from "@/lib/api";
import type { OpportunityDetail } from "@/lib/types";

/**
 * Opportunity detail.
 *
 * A Server Component fetches the opportunity itself (PRD section 6.3: default
 * to RSC for data fetching). Everything session-shaped -- the score breakdown
 * and the Ask panel -- is a client child, because it depends on state that
 * lives in the browser.
 */

export const dynamic = "force-dynamic";

async function fetchOpportunity(id: string): Promise<OpportunityDetail | null> {
  const numeric = Number(id);
  if (!Number.isInteger(numeric) || numeric <= 0) return null;
  try {
    const response = await fetch(`${API_BASE}/api/opportunities/${numeric}`, {
      cache: "no-store",
    });
    if (!response.ok) return null;
    return (await response.json()) as OpportunityDetail;
  } catch {
    // Backend down. Rendering "not found" would be a lie about the data, so
    // the client component reports the connection problem instead.
    return null;
  }
}

export default async function OpportunityPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const opportunity = await fetchOpportunity(id);
  if (!opportunity) notFound();
  return <OpportunityView opportunity={opportunity} />;
}
