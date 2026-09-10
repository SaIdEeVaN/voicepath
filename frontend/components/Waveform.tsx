"use client";

/**
 * The waveform (PRD section 2: "reacts to the user's actual voice").
 *
 * It is driven by live analyser data from the microphone, not a timer. That
 * distinction is the entire point of the component: a person speaking into a
 * screen needs to see that the machine is hearing *them*, and an animation
 * that moves whether or not they talk teaches them the opposite.
 *
 * Idle, it settles to a flat line rather than looping -- the stillness is what
 * makes the reaction legible when it starts.
 */

import { useEffect, useRef } from "react";

const BAR_COUNT = 48;

interface WaveformProps {
  /** Reads the current per-band levels. Returns [] when not recording. */
  read: () => number[];
  active: boolean;
}

export function Waveform({ read, active }: WaveformProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const barsRef = useRef<HTMLSpanElement[]>([]);
  // Smoothed heights live in a ref: this updates every frame, and routing it
  // through React state would re-render the tree 60 times a second.
  const heightsRef = useRef<number[]>(new Array(BAR_COUNT).fill(0));

  useEffect(() => {
    let frame = 0;
    let running = true;

    const reduceMotion =
      typeof window !== "undefined" &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    const tick = () => {
      if (!running) return;
      const levels = active ? read() : [];
      const heights = heightsRef.current;

      for (let i = 0; i < BAR_COUNT; i += 1) {
        const raw = levels[i] ?? 0;
        // Taper toward the edges so the shape reads as a voice rather than a
        // graphic equaliser.
        const centre = 1 - Math.abs(i / (BAR_COUNT - 1) - 0.5) * 1.1;
        const target = active ? Math.max(0.02, raw * centre) : 0.015;

        // Asymmetric smoothing: rise fast so a syllable lands immediately,
        // fall slowly so the trace stays readable between words.
        const previous = heights[i] ?? 0;
        const rate = target > previous ? 0.55 : 0.12;
        const next = previous + (target - previous) * (reduceMotion ? 1 : rate);
        heights[i] = next;

        const bar = barsRef.current[i];
        if (bar) {
          bar.style.height = `${Math.max(3, next * 168)}px`;
          bar.style.opacity = active ? "0.92" : "0.3";
        }
      }
      frame = requestAnimationFrame(tick);
    };

    frame = requestAnimationFrame(tick);
    return () => {
      running = false;
      cancelAnimationFrame(frame);
    };
  }, [read, active]);

  return (
    <div
      ref={containerRef}
      className="flex h-[170px] w-full items-center gap-1"
      aria-hidden="true"
    >
      {Array.from({ length: BAR_COUNT }, (_, i) => (
        <span
          key={i}
          ref={(element) => {
            if (element) barsRef.current[i] = element;
          }}
          className="min-w-0 flex-1 rounded-full transition-opacity duration-300"
          style={{
            height: "3px",
            opacity: 0.3,
            // Every seventh bar in the alternate hue, so the band reads as one
            // object with a rhythm rather than 48 separate elements.
            background:
              i % 7 === 0 ? "var(--color-accent-alt)" : "var(--color-accent)",
          }}
        />
      ))}
    </div>
  );
}
