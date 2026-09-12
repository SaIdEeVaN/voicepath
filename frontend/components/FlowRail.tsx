"use client";

/**
 * Where you are in the journey, shown two ways.
 *
 * The product is four screens with no breadcrumb between them, and the person
 * using it may not read the headings. Both forms mark the current step, label
 * it, and let you click back to a screen you have already filled. A step you
 * have not reached is not a link, because it would lead somewhere empty.
 *
 * **The rail**, down the left gutter, wherever the window is wide enough to
 * hold one beside the text. Measured: the content column maxes at 1180px, so
 * the gutter is 90px at 1280 and 130px at 1440, while the rail needs 178px.
 * Below 1536 it would sit on top of the words.
 *
 * It stayed 140px wide while being made more legible. Widening it to 150 was
 * tried and reverted: that pushes the requirement to 194px, which 1536 does
 * not have, so the rail would have vanished below 1728 -- paying for a little
 * more room with most of the screens able to show it at all. The size came
 * from type, weight, dot and spacing instead, all of which fit.
 *
 * **The bar**, under the header, everywhere else. Without it the flow vanished
 * entirely below 1536px -- which is most laptops and every phone. A stepper
 * that appears on some screens and not others is worse than one that changes
 * shape, because nobody can learn to rely on it.
 *
 * Both read `useFlowSteps`, so which step is current is decided once. Two
 * components working that out separately would drift, and the failure would be
 * silent: a stepper pointing at the wrong screen looks exactly like one
 * pointing at the right screen.
 */

import Link from "next/link";

import { copyFor } from "@/lib/i18n";
import { useFlowSteps, type FlowStep } from "@/lib/flow";
import { useSession } from "@/lib/session";

export function FlowRail() {
  const flow = useFlowSteps();
  const { language } = useSession();
  const copy = copyFor(language);

  if (!flow) return null;

  return (
    <nav
      aria-label={flow.steps.map((s) => s.label).join(", ")}
      /* Anchored to the content column rather than the viewport, so the gap
         beside the text stays constant as the window grows. */
      className="pointer-events-none fixed top-1/2 z-20 hidden w-[140px] -translate-y-1/2 2xl:block"
      style={{ left: "max(1.5rem, calc(50% - 768px))" }}
    >
      <ol className="flex flex-col">
        {flow.steps.map((step, index) => (
          <li key={step.href} className="flex flex-col">
            <div className="flex items-start gap-3.5">
              <Dot step={step} />
              <StepLabel step={step} language={language} big />
            </div>

            {step.isCurrent && (
              <span
                className="font-mono ml-[27px] mt-1.5 text-[11px] tracking-[0.07em]"
                style={{ color: "var(--color-accent-deep)" }}
                lang={language}
              >
                {copy.flowHere}
              </span>
            )}

            {/* The connector fills behind you: accent for ground covered, a
                hairline for what is still ahead. */}
            {index < flow.steps.length - 1 && (
              <span
                aria-hidden
                className="my-2 ml-[6px] w-[2px] flex-none rounded-full"
                style={{
                  height: step.isCurrent ? 24 : 28,
                  background: step.isPast
                    ? "var(--color-accent)"
                    : step.isCurrent
                      ? "var(--ink-22)"
                      : "var(--ink-09)",
                  opacity: step.isPast ? 0.5 : 1,
                }}
              />
            )}
          </li>
        ))}
      </ol>
    </nav>
  );
}

/**
 * The same flow laid flat, for every width the rail cannot fit.
 *
 * In the document rather than fixed, so it never covers anything, and it
 * scrolls sideways on a narrow phone rather than wrapping into two rows that
 * shift the page under a thumb.
 */
export function FlowBar() {
  const flow = useFlowSteps();
  const { language } = useSession();
  const copy = copyFor(language);

  if (!flow) return null;

  return (
    <nav
      aria-label={flow.steps.map((s) => s.label).join(", ")}
      className="border-b px-[7vw] py-3 2xl:hidden"
      style={{ borderColor: "var(--ink-09)", background: "var(--ink-03)" }}
    >
      <ol className="mx-auto flex w-full max-w-[1180px] items-center gap-2 overflow-x-auto">
        {flow.steps.map((step, index) => (
          <li key={step.href} className="flex flex-none items-center gap-2">
            <Dot step={step} inline />
            <StepLabel step={step} language={language} />
            {step.isCurrent && (
              <span
                className="font-mono hidden text-[10px] tracking-[0.07em] sm:inline"
                style={{ color: "var(--color-accent-deep)" }}
                lang={language}
              >
                · {copy.flowHere}
              </span>
            )}

            {index < flow.steps.length - 1 && (
              <span
                aria-hidden
                className="ml-1 h-[2px] w-6 flex-none rounded-full sm:w-10"
                style={{
                  background: step.isPast ? "var(--color-accent)" : "var(--ink-12)",
                  opacity: step.isPast ? 0.5 : 1,
                }}
              />
            )}
          </li>
        ))}
      </ol>
    </nav>
  );
}

function Dot({ step, inline = false }: { step: FlowStep; inline?: boolean }) {
  const size = step.isCurrent ? 13 : 9;
  return (
    <span
      aria-hidden
      className="flex-none rounded-full"
      style={{
        width: size,
        height: size,
        marginTop: inline ? 0 : step.isCurrent ? 4 : 6,
        background:
          step.isCurrent || step.isPast
            ? "var(--color-accent)"
            : "var(--ink-12)",
        opacity: step.isPast && !step.isCurrent ? 0.45 : 1,
        // A ring on the current step, so it reads as the one being stood on
        // rather than just a darker dot.
        boxShadow: step.isCurrent
          ? "0 0 0 4px color-mix(in srgb, var(--color-accent) 18%, transparent)"
          : "none",
      }}
    />
  );
}

function StepLabel({
  step,
  language,
  big = false,
}: {
  step: FlowStep;
  language: string;
  big?: boolean;
}) {
  const text = (
    <span
      className={`${big ? "text-[15px]" : "text-[13px]"} whitespace-nowrap leading-snug`}
      style={{
        color: step.isCurrent
          ? "var(--color-ink)"
          : step.isPast
            ? "var(--ink-62)"
            : "var(--ink-38)",
        fontWeight: step.isCurrent ? 600 : 400,
      }}
      lang={language}
    >
      {step.label}
    </span>
  );

  return step.canGo ? (
    <Link
      href={step.href}
      className="pointer-events-auto underline-offset-4 hover:underline"
    >
      {text}
    </Link>
  ) : (
    text
  );
}
