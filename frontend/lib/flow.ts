"use client";

/**
 * Where someone is in the four-screen journey.
 *
 * One source of truth, because the flow is shown two ways: a vertical rail in
 * the left gutter where there is room for one, and a compact bar under the
 * header where there is not. Two components deriving "which step is this"
 * separately would drift, and the failure would be silent -- a stepper
 * pointing at the wrong screen looks exactly like one pointing at the right
 * one.
 */

import { usePathname } from "next/navigation";

import { copyFor } from "./i18n";
import { useSession } from "./session";

export const FLOW_STEPS = [
  "/speak",
  "/understanding",
  "/schemes",
  "/passport",
] as const;

export interface FlowStep {
  href: string;
  label: string;
  isCurrent: boolean;
  isPast: boolean;
  /** Reachable means it has something on it, not merely that it exists. */
  canGo: boolean;
}

/** Null when this page is not part of the flow at all. */
export function useFlowSteps(): { steps: FlowStep[]; current: number } | null {
  const pathname = usePathname();
  const { language, sessionId, skills } = useSession();
  const copy = copyFor(language);

  // The disambiguation screen belongs to "what I heard" and a scheme's detail
  // page to "what fits"; neither is a step of its own.
  const current = FLOW_STEPS.findIndex(
    (step) => pathname === step || pathname?.startsWith(`${step}/`),
  );
  if (current === -1) return null;

  const steps = FLOW_STEPS.map((href, index) => {
    const reachable =
      index === 0
        ? true
        : !sessionId
          ? false
          : index >= 2
            ? skills.length > 0
            : true;

    return {
      href,
      label: copy.flowSteps[index] ?? "",
      isCurrent: index === current,
      isPast: index < current,
      canGo: index !== current && reachable,
    };
  });

  return { steps, current };
}
