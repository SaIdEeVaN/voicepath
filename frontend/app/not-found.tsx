import Link from "next/link";

export default function NotFound() {
  return (
    <section className="flex flex-1 flex-col items-center justify-center gap-5 px-[7vw] py-20 text-center">
      <h1 className="vp-display text-[clamp(1.75rem,3.2vw,2.5rem)]">
        There is nothing at this address.
      </h1>
      <p className="max-w-[32em] text-[15px]" style={{ color: "var(--ink-62)" }}>
        The page you were looking for has moved or never existed.
      </p>
      <Link href="/" className="vp-pill vp-pill-primary mt-2">
        Start again
      </Link>
    </section>
  );
}
