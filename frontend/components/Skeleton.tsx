/**
 * Placeholders in the shape of what is coming (2026-11-05).
 *
 * A bare "Loading..." title said something was happening but not what; rows
 * and cards in the shape of the results say what, and keep the page from
 * jumping when they arrive. Decorative: screen readers hear the list's
 * aria-busy instead. The shimmer stops under prefers-reduced-motion (the
 * global rule in globals.css).
 */

export function RowSkeletons({ count = 3 }: { count?: number }) {
  return (
    <>
      {Array.from({ length: count }, (_, index) => (
        <div
          key={index}
          aria-hidden="true"
          className="vp-skeleton-card flex items-start gap-7 rounded-[16px] p-7 max-[560px]:flex-col max-[560px]:gap-4 max-[560px]:p-5"
        >
          <span className="vp-skeleton h-[64px] w-[64px] flex-none rounded-full" />
          <div className="flex min-w-0 flex-1 flex-col gap-3">
            <span className="vp-skeleton h-6 w-3/5 rounded-md" />
            <span className="vp-skeleton h-3.5 w-2/5 rounded-md" />
            <span className="vp-skeleton mt-1 h-3.5 w-4/5 rounded-md" />
            <span className="vp-skeleton h-3.5 w-3/4 rounded-md" />
          </div>
        </div>
      ))}
    </>
  );
}

export function CardSkeletons({ count = 2 }: { count?: number }) {
  return (
    <>
      {Array.from({ length: count }, (_, index) => (
        <div
          key={index}
          aria-hidden="true"
          className="vp-skeleton-card flex flex-col gap-3.5 rounded-[14px] p-[1.375rem]"
        >
          <span className="vp-skeleton h-6 w-1/2 rounded-md" />
          <span className="vp-skeleton h-5 w-1/4 rounded-full" />
          <span className="vp-skeleton h-[64px] w-full rounded-[10px]" />
        </div>
      ))}
    </>
  );
}
