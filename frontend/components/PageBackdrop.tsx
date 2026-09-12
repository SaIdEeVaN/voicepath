/**
 * Ambient marks behind every page.
 *
 * The screens are mostly one column of content on a flat cream field, and on a
 * wide monitor that reads as empty rather than calm. This gives the page
 * something to sit on.
 *
 * Every mark is the product's own vocabulary rather than decoration borrowed
 * from somewhere else: concentric rings are what the microphone does when it is
 * listening, and the waveform is what a person's voice looks like on the speak
 * screen -- along the bottom, and stood on its end down both side gutters.
 * Someone who has used it once will recognise all of it.
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

      {/* A margin rule down the right gutter.
      
          The left one is gone: `FlowRail` puts the four steps of the journey
          there instead, which is content rather than decoration and is what
          that space was actually wanted for.
      
          The sides were the emptiest part of a wide screen: the content is a
          centred column, so above about 1024px there is real space either
          edge doing nothing. A hairline that fades at both ends reads as the
          page having margins rather than as a line drawn on it.
      
          The ticks along each rule are the waveform again, stood on its end --
          the same amplitude marks the speak screen draws, at rest.
      
          Hidden below `lg`. Measured, the gutter is 72px at 1024 and 90px at
          1280, which is room for a rule 28px from the edge; below that the
          content reaches the edge and there is no gutter to decorate. */}
      {(["right"] as const).map((side) => (
        <svg
          key={side}
          className="absolute inset-y-[12vh] right-7 hidden w-6 lg:block"
          viewBox="0 0 24 600"
          preserveAspectRatio="none"
          fill="none"
        >
          <defs>
            <linearGradient id={`vp-rule-${side}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="var(--color-accent)" stopOpacity="0" />
              <stop offset="22%" stopColor="var(--color-accent)" stopOpacity="0.16" />
              <stop offset="78%" stopColor="var(--color-accent)" stopOpacity="0.16" />
              <stop offset="100%" stopColor="var(--color-accent)" stopOpacity="0" />
            </linearGradient>
          </defs>

          <line
            x1="12"
            y1="0"
            x2="12"
            y2="600"
            stroke={`url(#vp-rule-${side})`}
            strokeWidth="1"
          />

          {/* Amplitudes, not decoration: short marks where a quiet passage
              would sit, longer where a loud one would. */}
          {(
            [
              [92, 4], [140, 9], [188, 5], [236, 12], [284, 6],
              [332, 10], [380, 4], [428, 8], [476, 5],
            ] as [number, number][]
          ).map(([y, len]) => (
            <line
              key={y}
              x1={12 - len / 2}
              y1={y}
              x2={12 + len / 2}
              y2={y}
              stroke="var(--color-accent)"
              strokeOpacity="0.14"
              strokeWidth="1"
            />
          ))}
        </svg>
      ))}

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
