"use client";

/**
 * The match percentage, drawn as a filled ring.
 *
 * A conic gradient rather than an SVG arc: it is one element, it animates
 * cheaply, and the filled proportion is legible at a glance without reading
 * the number -- which matters for someone who reads slowly or not at all.
 *
 * It fills from empty on first paint. That is not decoration: the ring is the
 * only place the score appears as a quantity rather than a numeral, and
 * watching it stop somewhere is what makes 62% and 97% feel different to
 * someone who does not read the digits. It happens once, on arrival, and never
 * again -- `prefers-reduced-motion` collapses the transition to nothing
 * through the global rule in globals.css, leaving the final angle.
 */

import { useEffect, useState } from "react";

export function MatchRing({
  score,
  size = 74,
}: {
  /** Fraction in [0, 1]. */
  score: number;
  size?: number;
}) {
  const percent = Math.round(Math.min(1, Math.max(0, score)) * 100);
  const degrees = (percent / 100) * 360;
  const inner = size - 14;

  // Starts empty, fills to the real angle once mounted. Two frames rather than
  // one: a state set inside the first commit can be batched into it, and the
  // ring would render already full with nothing to transition from.
  const [filled, setFilled] = useState(false);
  useEffect(() => {
    const frame = requestAnimationFrame(() =>
      requestAnimationFrame(() => setFilled(true)),
    );
    return () => cancelAnimationFrame(frame);
  }, []);

  return (
    <div
      className="grid flex-none place-items-center rounded-full"
      style={{
        width: size,
        height: size,
        // The angle is a registered property (@property --vp-deg), so it
        // interpolates as an angle instead of snapping as a string.
        ["--vp-deg" as string]: `${filled ? degrees : 0}deg`,
        background:
          "conic-gradient(var(--color-accent) var(--vp-deg), var(--ink-09) 0)",
        transition: "--vp-deg 0.85s cubic-bezier(0.22, 1, 0.36, 1)",
      }}
      role="img"
      aria-label={`${percent} percent`}
    >
      <span
        className="font-display grid place-items-center rounded-full tracking-[-0.02em]"
        style={{
          width: inner,
          height: inner,
          background: "var(--color-surface)",
          fontSize: size > 60 ? 19 : 15,
        }}
      >
        {percent}
      </span>
    </div>
  );
}
