/**
 * The match percentage, drawn as a filled ring.
 *
 * A conic gradient rather than an SVG arc: it is one element, it animates
 * cheaply, and the filled proportion is legible at a glance without reading
 * the number -- which matters for someone who reads slowly or not at all.
 */

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

  return (
    <div
      className="grid flex-none place-items-center rounded-full"
      style={{
        width: size,
        height: size,
        background: `conic-gradient(var(--color-accent) ${degrees}deg, var(--ink-09) 0)`,
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
