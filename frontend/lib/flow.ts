"use client";

/**
 * Where someone is in the journey.
 *
 * One source of truth, because the flow is shown two ways: a vertical rail in
 * the left gutter where there is room for one, and a compact bar under the
 * header where there is not. Two components deriving "which step is this"
 * separately would drift, and the failure would be silent -- a stepper
 * pointing at the wrong screen looks exactly like one pointing at the right
 * screen.
 *
 * **The order here is the order the buttons actually take you in**, which is
 * the whole point of a stepper and is what it got wrong until 2026-09-12. It
 * listed the scheme list before the passport, while `/understanding`'s confirm
 * button goes to `/passport` and the passport's own button goes on to
 * `/schemes`. A stepper describing a flow the app does not have is worse than
 * no stepper: it is a confident wrong answer to "where am I".
 *
 * If a navigation button is ever repointed, this list has to move with it.
 */

import { usePathname } from "next/navigation";

import { copyFor } from "./i18n";
import { useSession } from "./session";

/**
 * Speak, hear it back, keep it, then look at what fits and open one.
 *
 * The last has no path of its own: a scheme detail page needs an id, so it is
 * somewhere you arrive from the list rather than somewhere you can be sent.
 * It is still a step -- it is what the whole journey is for.
 */
export const FLOW_STEPS: readonly (string | null)[] = [
  "/speak",
  "/understanding",
  "/passport",
  "/schemes",
  null,
];

export interface FlowStep {
  /** Null where the step cannot be navigated to directly. */
  href: string | null;
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

  const current = currentStep(pathname);
  if (current === -1) return null;

  const steps = FLOW_STEPS.map((href, index) => ({
    href,
    label: copy.flowSteps[index] ?? "",
    isCurrent: index === current,
    isPast: index < current,
    canGo: href !== null && index !== current && reachable(index, sessionId, skills.length),
  }));

  return { steps, current };
}

function currentStep(pathname: string | null): number {
  if (!pathname) return -1;

  // A scheme's own page is the last step, not part of the list before it.
  // Checked first, because it also starts with `/schemes`.
  if (/^\/schemes\/[^/]+$/.test(pathname)) return 4;

  // The disambiguation screen belongs to "what I heard" rather than being a
  // step of its own -- it is the same question asked more closely.
  if (pathname.startsWith("/understanding")) return 1;

  const index = FLOW_STEPS.indexOf(pathname);
  return index;
}

function reachable(index: number, sessionId: string | null, skillCount: number): boolean {
  if (index === 0) return true;
  if (!sessionId) return false;
  // The passport and the list both read the skills. Sending someone to either
  // before anything has been understood lands them on an empty screen.
  if (index >= 2) return skillCount > 0;
  return true;
}
