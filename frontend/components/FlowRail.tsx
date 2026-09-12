"use client";

/**
 * Where you are, down the left of a wide screen.
 *
 * The product is four screens with no breadcrumb between them, and the person
 * using it may not read the headings. On a phone that is survivable because
 * each screen fills the view; on a monitor the content is a centred column and
 * the left gutter was doing nothing at all.
 *
 * So this is content rather than decoration: the four steps, the one you are
 * on marked, and the ones behind you clickable so you can go back and change
 * something without losing your place. A step you have not reached yet is not
 * a link -- offering it would send someone to a screen with nothing on it.
 *
 * Only on the flow itself. The landing page, About and admin are not steps in
 * anything, and a progress rail beside them would be claiming otherwise.
 */

import Link from "next/link";
import { usePathname } from "next/navigation";

import { copyFor } from "@/lib/i18n";
import { useSession } from "@/lib/session";

const STEPS = ["/speak", "/understanding", "/schemes", "/passport"] as const;

export function FlowRail() {
  const pathname = usePathname();
  const { language, sessionId, skills } = useSession();
  const copy = copyFor(language);

  // The disambiguation screen belongs to "what I heard", and a scheme's detail
  // page belongs to "what fits" -- neither is a step of its own.
  const current = STEPS.findIndex(
    (step) => pathname === step || pathname?.startsWith(`${step}/`),
  );
  if (current === -1) return null;

  /** Reachable means it has something on it, not merely that it exists. */
  const reachable = (index: number) => {
    if (index === 0) return true;
    if (!sessionId) return false;
    if (index >= 2) return skills.length > 0;
    return true;
  };

  return (
    <nav
      aria-label={copy.flowSteps.join(", ")}
      /* Anchored to the content column, not the viewport, so the gap beside
         the text stays constant as the window grows.
      
         `2xl` because that is where it measurably fits. The container maxes at
         1180px, so the gutter is 90px at 1280 and 130px at 1440 -- and a rail
         with readable text in it needs about 178px. Below 1536 it would sit on
         top of the words, which is worse than an empty margin. */
      className="pointer-events-none fixed top-1/2 z-20 hidden w-[140px] -translate-y-1/2 2xl:block"
      style={{ left: "max(1.5rem, calc(50% - 768px))" }}
    >
      <ol className="flex flex-col gap-0">
        {copy.flowSteps.map((label, index) => {
          const href = STEPS[index];
          if (!href) return null;
          const isCurrent = index === current;
          const isPast = index < current;
          const canGo = !isCurrent && reachable(index);

          const dot = (
            <span
              aria-hidden
              className="mt-[7px] h-[7px] w-[7px] flex-none rounded-full"
              style={{
                background: isCurrent
                  ? "var(--color-accent)"
                  : isPast
                    ? "var(--ink-38)"
                    : "var(--ink-12)",
              }}
            />
          );

          const text = (
            <span
              className="text-[13px] leading-snug"
              style={{
                color: isCurrent
                  ? "var(--color-ink)"
                  : isPast
                    ? "var(--ink-62)"
                    : "var(--ink-38)",
                fontWeight: isCurrent ? 500 : 400,
              }}
              lang={language}
            >
              {label}
            </span>
          );

          return (
            <li key={label} className="flex flex-col">
              <div className="flex items-start gap-3">
                {dot}
                {canGo ? (
                  <Link
                    href={href}
                    className="pointer-events-auto underline-offset-4 hover:underline"
                  >
                    {text}
                  </Link>
                ) : (
                  text
                )}
              </div>

              {isCurrent && (
                <span
                  className="font-mono ml-[19px] mt-1 text-[10px] tracking-[0.08em]"
                  style={{ color: "var(--ink-38)" }}
                  lang={language}
                >
                  {copy.flowHere}
                </span>
              )}

              {/* The line between steps, drawn only between them. */}
              {index < STEPS.length - 1 && (
                <span
                  aria-hidden
                  className="my-1 ml-[3px] h-6 w-px flex-none"
                  style={{
                    background: index < current ? "var(--ink-22)" : "var(--ink-09)",
                  }}
                />
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
