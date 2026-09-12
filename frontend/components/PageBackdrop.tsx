/**
 * Ambient marks behind every page.
 *
 * The screens are mostly one column of content on a flat cream field, and on a
 * wide monitor that reads as empty rather than calm. This gives the page
 * something to sit on.
 *
 * Both marks are the product's own vocabulary rather than decoration borrowed
 * from somewhere else: concentric rings are what the microphone does when it is
 * listening, and the waveform is what a person's voice looks like on the speak
 * screen. Someone who has used it once will recognise both.
 *
 * Deliberately almost invisible -- the accent at four to seven per cent. The
 * microphone is where this product spends its boldness, and a backdrop that
 * competes with it would cost more than the flatness does. If you notice these
 * before you notice the mic, they are wrong.
 *
 * Static SVG, no script and no animation: the target device is a cheap Android
 * phone, and ambient motion behind every screen is exactly the kind of thing
 * that makes one feel slow. `fixed`, so it does not repaint on scroll.
 */

export function PageBackdrop() {
  return (
    <div
      aria-hidden
      // z-0 with the content at z-10, rather than a negative index. A
      // negative z-index paints behind the parent's background, and the
      // body background here propagates to the canvas, which makes the
      // result depend on painting rules nobody should have to reason about.
      className="pointer-events-none fixed inset-0 z-0 overflow-hidden"
    >
      {/* Listening rings, off the top-right corner. Cropped by the viewport on
          purpose -- a complete circle reads as an object on the page, a
          cropped one reads as the page having an edge. */}
      <svg
        className="absolute -right-[18vw] -top-[22vw] h-[62vw] w-[62vw] max-h-[760px] max-w-[760px] min-h-[320px] min-w-[320px]"
        viewBox="0 0 400 400"
        fill="none"
      >
        {[80, 128, 176, 200].map((r, i) => (
          <circle
            key={r}
            cx="200"
            cy="200"
            r={r}
            stroke="var(--color-accent)"
            strokeOpacity={0.07 - i * 0.012}
            strokeWidth="1"
          />
        ))}
      </svg>

      {/* A voice, along the bottom. Hidden on narrow screens: on a phone the
          content already reaches both edges and there is no emptiness to fill,
          so this would only be clutter behind the text. */}
      <svg
        className="absolute bottom-[8vh] left-0 hidden h-[120px] w-full md:block"
        viewBox="0 0 1200 120"
        preserveAspectRatio="none"
        fill="none"
      >
        <path
          d="M0 60 Q 40 60 60 60 T 120 60 Q 150 22 170 60 T 210 60 Q 240 88 260 60
             T 320 60 Q 350 34 372 60 T 430 60 Q 462 78 486 60 T 548 60
             Q 580 16 604 60 T 668 60 Q 700 92 726 60 T 790 60 Q 820 40 846 60
             T 910 60 Q 942 74 966 60 T 1030 60 Q 1062 30 1086 60 T 1150 60
             Q 1176 60 1200 60"
          stroke="var(--color-accent)"
          strokeOpacity="0.09"
          strokeWidth="1.5"
          strokeLinecap="round"
        />
      </svg>

      {/* A single soft wash anchored to the rings, so the top-right corner has
          depth rather than a floating line drawing. Not a wash across the
          section -- it belongs to the rings and goes nowhere else. */}
      <div
        className="absolute -right-[10vw] -top-[14vw] h-[52vw] w-[52vw] max-h-[620px] max-w-[620px] rounded-full"
        style={{
          background:
            "radial-gradient(circle, color-mix(in srgb, var(--color-accent) 6%, transparent) 0%, transparent 70%)",
        }}
      />
    </div>
  );
}
