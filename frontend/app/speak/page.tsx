"use client";

/**
 * Voice capture (PRD section 4.1).
 *
 * Capture and transcription are separate steps here, as the PRD requires.
 * Which transcriber runs depends on what is configured:
 *
 *   server-side STT available -> record a blob, POST it, discard the blob
 *   not available             -> recognise on-device, send only the text
 *
 * Either way the microphone is released the moment recording ends, and the
 * audio blob is dropped as soon as the transcript comes back. Nothing on this
 * screen writes audio anywhere.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";

import { ErrorNote } from "@/components/Notices";
import { Waveform } from "@/components/Waveform";
import { ApiError, api } from "@/lib/api";
import {
  canRecogniseOnDevice,
  startRecognition,
  type RecognitionHandle,
} from "@/lib/browser-speech";
import { copyFor } from "@/lib/i18n";
import { isRecordingSupported, startRecording, type Recorder } from "@/lib/recorder";
import { useSession } from "@/lib/session";
import { fromError, problem, problemText, type Problem } from "@/lib/problems";

type Phase = "idle" | "listening" | "working" | "error";

export default function SpeakPage() {
  const router = useRouter();
  const { language, setSession, health, healthUnreachable, healthWaking } =
    useSession();
  const copy = copyFor(language);

  const [phase, setPhase] = useState<Phase>("idle");
  const [transcript, setTranscript] = useState("");
  const [error, setError] = useState<Problem | null>(null);

  const recorderRef = useRef<Recorder | null>(null);
  const recognitionRef = useRef<RecognitionHandle | null>(null);
  const finalTranscriptRef = useRef("");

  // Null until /health answers. Until then we do not know which path to take,
  // so the button waits rather than guessing wrong and losing the recording.
  const serverStt = health ? !health.degraded.includes("stt") : null;

  const readLevels = useCallback(
    () => recorderRef.current?.levels(48) ?? [],
    [],
  );

  const releaseAll = useCallback(() => {
    recognitionRef.current?.abort();
    recognitionRef.current = null;
    recorderRef.current?.cancel();
    recorderRef.current = null;
  }, []);

  // Leaving mid-recording must not leave the microphone open.
  useEffect(() => releaseAll, [releaseAll]);

  const submitTranscript = useCallback(
    async (text: string, detected: string) => {
      const clean = text.trim();
      if (!clean) {
        setPhase("error");
        setError(problem("nothingHeard"));
        return;
      }
      try {
        setPhase("working");
        const result = await api.clientTranscript(clean, detected);
        setSession(result.session_id, result.transcript, language);
        router.push("/understanding");
      } catch (cause) {
        setPhase("error");
        setError(fromError(cause));
      }
    },
    [copy.nothingHeard, language, router, setSession],
  );

  const start = useCallback(async () => {
    setError(null);
    setTranscript("");
    finalTranscriptRef.current = "";

    if (serverStt) {
      if (!isRecordingSupported()) {
        setPhase("error");
        setError(problem("micUnsupported"));
        return;
      }
      try {
        recorderRef.current = await startRecording();
        setPhase("listening");
      } catch (cause) {
        const reason = (cause as { reason?: string }).reason;
        setPhase("error");
        setError(problem(reason === "denied" ? "micDenied" : "micUnsupported"));
      }
      return;
    }

    // On-device path. Recording runs alongside recognition purely so the
    // waveform has real levels to draw -- that blob is never uploaded.
    if (!canRecogniseOnDevice()) {
      setPhase("error");
      setError(problem("micUnsupported"));
      return;
    }

    if (isRecordingSupported()) {
      try {
        recorderRef.current = await startRecording();
      } catch {
        /* Levels are a nicety; recognition can proceed without them. */
      }
    }

    recognitionRef.current = startRecognition(language, {
      onPartial: (text) => setTranscript(text),
      onError: (reason) => {
        if (reason === "no-speech") return;
        setPhase("error");
        setError(problem(reason === "not-allowed" ? "micDenied" : "micUnsupported"));
        releaseAll();
      },
      onEnd: (finalText) => {
        finalTranscriptRef.current = finalText;
      },
    });

    if (recognitionRef.current) setPhase("listening");
  }, [copy.micDenied, copy.micUnsupported, language, releaseAll, serverStt]);

  const stop = useCallback(async () => {
    if (phase !== "listening") return;

    if (serverStt) {
      setPhase("working");
      const recorder = recorderRef.current;
      recorderRef.current = null;
      const blob = await recorder?.stop();
      if (!blob) {
        setPhase("error");
        setError(problem("nothingHeard"));
        return;
      }
      try {
        const result = await api.transcribe(blob, language);
        // The blob goes out of scope here and is never persisted.
        setSession(result.session_id, result.transcript, language);
        router.push("/understanding");
      } catch (cause) {
        if (cause instanceof ApiError && cause.isUnavailable) {
          // Server-side STT went away between /health and now.
          setPhase("error");
          setError(fromError(cause));
          return;
        }
        setPhase("error");
        setError(fromError(cause));
      }
      return;
    }

    setPhase("working");
    recognitionRef.current?.stop();
    recorderRef.current?.cancel();
    recorderRef.current = null;

    // Recognition settles its last segment asynchronously; give it a beat
    // before reading, then fall back to what is already on screen.
    setTimeout(() => {
      void submitTranscript(
        finalTranscriptRef.current || transcript,
        language,
      );
    }, 350);
  }, [
    copy.nothingHeard,
    language,
    phase,
    router,
    serverStt,
    setSession,
    submitTranscript,
    transcript,
  ]);

  const listening = phase === "listening";
  const working = phase === "working";

  return (
    // On a phone the mic button used to sit half below the fold under 300px
    // of waveform and empty transcript; the spacing shrinks there so it is
    // where a thumb finds it, and the instruction above it is readable size.
    <section className="flex flex-1 flex-col items-center justify-center gap-6 px-[7vw] py-[clamp(1.5rem,5vw,3.5rem)] sm:gap-11">
      <div
        className="flex items-center gap-2.5 text-[15px] sm:text-[14px]"
        style={{ color: "var(--ink-62)" }}
      >
        <span
          className="h-[7px] w-[7px] rounded-full"
          style={{
            background: listening
              ? "var(--color-accent)"
              : "var(--ink-22)",
          }}
        />
        <span lang={language}>
          {working ? copy.thinking : listening ? copy.listening : copy.speakHint}
        </span>
        {listening && (
          <span
            className="font-mono rounded px-2 py-0.5 tracking-[0.06em]"
            style={{ background: "var(--ink-04)" }}
          >
            {language.toUpperCase()}
          </span>
        )}
      </div>

      <div className="grid h-[110px] w-full max-w-[820px] place-items-center sm:h-[180px]">
        <Waveform read={readLevels} active={listening} />
      </div>

      {/* Live transcript, only on the on-device path -- server-side STT has
          nothing to show until the recording is sent. */}
      <div
        className="font-display min-h-[64px] w-full max-w-[760px] text-center text-[clamp(1.4rem,2.4vw,2.1rem)] leading-snug tracking-[-0.02em] sm:min-h-[120px]"
        style={{ textWrap: "pretty" }}
        lang={language}
        aria-live="polite"
      >
        {transcript}
        {listening && !serverStt && (
          <span className="vp-caret" style={{ color: "var(--color-accent)" }}>
            |
          </span>
        )}
      </div>

      {healthWaking && !error && (
        <div
          className="w-full max-w-[560px] text-center text-[13.5px]"
          style={{ color: "var(--ink-55)" }}
          lang={language}
        >
          {copy.serverWaking}
        </div>
      )}

      {(error || healthUnreachable) && (
        <div className="w-full max-w-[560px]">
          <ErrorNote message={problemText(error, language) ?? copy.serverUnreachable} />
        </div>
      )}

      <div className="flex flex-col items-center gap-3.5">
        {listening ? (
          <button
            type="button"
            onClick={() => void stop()}
            className="grid h-[92px] w-[92px] place-items-center rounded-full transition-transform hover:scale-105"
            style={{ background: "var(--color-ink)", color: "var(--color-paper)" }}
          >
            <span
              className="h-[22px] w-[22px] rounded-[5px]"
              style={{ background: "currentColor" }}
            />
            <span className="sr-only">{copy.stopHint}</span>
          </button>
        ) : (
          <button
            type="button"
            onClick={() => void start()}
            disabled={working || serverStt === null}
            className="relative grid h-[92px] w-[92px] place-items-center rounded-full transition-transform hover:scale-105 disabled:opacity-40"
            style={{ background: "var(--color-accent)", color: "var(--color-paper)" }}
          >
            {!working && serverStt !== null && (
              <span
                className="vp-breathe pointer-events-none absolute -inset-1 rounded-full border"
                style={{ borderColor: "var(--color-accent)" }}
              />
            )}
            <svg
              viewBox="0 0 24 24"
              width={30}
              height={30}
              fill="none"
              stroke="currentColor"
              strokeWidth={1.5}
              strokeLinecap="round"
              aria-hidden="true"
            >
              <rect x="9" y="3" width="6" height="11" rx="3" />
              <path d="M5.5 11.5a6.5 6.5 0 0 0 13 0" />
              <path d="M12 18v3.2" />
            </svg>
            <span className="sr-only">{copy.speakHint}</span>
          </button>
        )}

        {/* Only while recording: before that the line above already says what
            to do, and saying it twice pushed the button further down. */}
        {listening && (
          <p className="text-[14px]" style={{ color: "var(--ink-55)" }} lang={language}>
            {copy.stopHint}
          </p>
        )}
      </div>
    </section>
  );
}
