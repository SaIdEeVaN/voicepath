import { notFound } from "next/navigation";

import { SchemeView } from "./SchemeView";
import { API_BASE } from "@/lib/api";
import type { SchemeDetail } from "@/lib/types";

/**
 * Scheme detail.
 *
 * A Server Component fetches the scheme itself (PRD section 6.3: default
 * to RSC for data fetching). Everything session-shaped -- the score breakdown
 * and the Ask panel -- is a client child, because it depends on state that
 * lives in the browser.
 */

export const dynamic = "force-dynamic";

async function fetchScheme(id: string): Promise<SchemeDetail | null> {
  const numeric = Number(id);
  if (!Number.isInteger(numeric) || numeric <= 0) return null;
  try {
    const response = await fetch(`${API_BASE}/api/schemes/${numeric}`, {
      cache: "no-store",
    });
    if (!response.ok) return null;
    return (await response.json()) as SchemeDetail;
  } catch {
    // Backend down. Rendering "not found" would be a lie about the data, so
    // the client component reports the connection problem instead.
    return null;
  }
}

export default async function SchemePage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const scheme = await fetchScheme(id);
  if (!scheme) notFound();
  return <SchemeView scheme={scheme} />;
}
