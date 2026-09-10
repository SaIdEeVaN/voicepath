"use client";

/**
 * "Ask VoicePath" -- spoken follow-up Q&A (PRD section 4.6).
 *
 * Voice in, voice out, with the text kept visible so nothing depends on
 * hearing it. Each answer carries the note saying where it came from, which is
 * the same trust move as the evidence quote on a skill card: the person can
 * always see what the answer rests on.
 *
 * When an answer could not be found in the data it is marked, rather than
 * dressed up. "I do not have that" is a real answer here.
 */

import { useCallback, useEffect, useRef, useState } from "react";

import { MicIcon } from "@/components/MicIcon";
import { ApiError, api } from "@/lib/api";
import {
  canRecogniseOnDevice,
  playBase64Audio,
  speakOnDevice,
  startRecognition,
  stopSpeaking,
  type RecognitionHandle,
} from "@/lib/browser-speech";
import { copyFor } from "@/lib/i18n";
import { useSession } from "@/lib/session";
import type { Language } from "@/lib/types";

interface Exchange {
  question: string;
  answer: string;
  sourceNote: string;
  fromData: boolean;
}

export function AskVoicePath({ opportunityId }: { opportunityId: number }) {
  const { language, sessionId } = useSession();
  const copy = copyFor(language);

  const [exchanges, setExchanges] = useState<Exchange[]>([]);
  const [listening, setListening] = useState(false);
  const [thinking, setThinking] = useState(false);
  const [draft, setDraft] = useState("");
  const [error, setError] = useState<string | null>(null);

  const recognitionRef = useRef<RecognitionHandle | null>(null);
  const canListen = canRecogniseOnDevice();

  useEffect(
    () => () => {
      recognitionRef.current?.abort();
      stopSpeaking();
    },
    [],
  );

  const ask = useCallback(
    async (question: string) => {
      const clean = question.trim();
      if (!clean) return;

      setThinking(true);
      setError(null);
      setDraft("");
      try {
        const result = await api.ask({
          sessionId,
          opportunityId,
          question: clean,
          language: language as Language,
        });

        setExchanges((previous) => [
          ...previous,
          {
            question: clean,
            answer: result.answer_text,
            sourceNote: result.source_note,
            fromData: result.answered_from_data,
          },
        ]);

        // Speak it. Server TTS when configured, on-device otherwise -- both
        // are real speech, so the answer is heard either way.
        try {
          const speech = await api.synthesize(result.answer_text, language as Language);
          if (speech.audio_base64) await playBase64Audio(speech.audio_base64);
          else if (speech.use_browser_tts) {
            await speakOnDevice(result.answer_text, language as Language);
          }
        } catch {
          await speakOnDevice(result.answer_text, language as Language);
        }
      } catch (cause) {
        setError(
          cause instanceof ApiError ? cause.message : "Something went wrong.",
        );
      } finally {
        setThinking(false);
      }
    },
    [language, opportunityId, sessionId],
  );

  const toggleListening = useCallback(() => {
    if (listening) {
      recognitionRef.current?.stop();
      recognitionRef.current = null;
      setListening(false);
      return;
    }
    if (!canListen) return;

    stopSpeaking();
    setError(null);
    setDraft("");

    recognitionRef.current = startRecognition(language as Language, {
      onPartial: (text) => setDraft(text),
      onError: (reason) => {
        setListening(false);
        if (reason === "not-allowed") setError(copy.micDenied);
        else if (reason !== "no-speech") setError(copy.micUnsupported);
      },
      onEnd: (finalText) => {
        setListening(false);
        if (finalText.trim()) void ask(finalText);
      },
    });
    if (recognitionRef.current) setListening(true);
  }, [ask, canListen, copy.micDenied, copy.micUnsupported, language, listening]);

  return (
    <aside
      className="sticky top-[78px] flex flex-col gap-5 rounded-[16px] p-6"
      style={{ background: "var(--color-ink)", color: "var(--color-paper)" }}
    >
      <header className="flex items-center gap-3">
        <span
          className="grid h-[34px] w-[34px] flex-none place-items-center rounded-full"
          style={{ background: "var(--color-accent)", color: "var(--color-ink)" }}
        >
          <MicIcon size={17} strokeWidth={1.7} />
        </span>
        <h2 className="text-[15px] font-medium" lang={language}>
          {copy.askTitle}
        </h2>
      </header>

      <div className="flex flex-col gap-4" aria-live="polite">
        {exchanges.map((exchange, index) => (
          <div key={index} className="vp-rise flex flex-col gap-2">
            <p
              className="max-w-[88%] self-end rounded-[14px_14px_4px_14px] px-4 py-2.5 text-[14.5px] leading-snug"
              style={{ background: "var(--paper-12)" }}
              lang={language}
            >
              {exchange.question}
            </p>
            <p
              className="max-w-[92%] self-start rounded-[14px_14px_14px_4px] px-4 py-3 text-[14.5px] leading-relaxed"
              style={{ background: "var(--paper-05)" }}
              lang={language}
            >
              {exchange.answer}
            </p>
            <p
              className="font-mono flex items-center gap-2 self-start text-[10.5px] tracking-[0.05em]"
              style={{
                color: exchange.fromData
                  ? "var(--paper-40)"
                  : "var(--color-caution)",
              }}
              lang={language}
            >
              <span
                className="h-0 w-0"
                style={{
                  borderLeft: "6px solid currentColor",
                  borderTop: "4px solid transparent",
                  borderBottom: "4px solid transparent",
                }}
              />
              {exchange.sourceNote}
            </p>
          </div>
        ))}

        {draft && (
          <p
            className="max-w-[88%] self-end rounded-[14px_14px_4px_14px] px-4 py-2.5 text-[14.5px] italic leading-snug"
            style={{ background: "var(--paper-08)" }}
          >
            {draft}
          </p>
        )}

        {thinking && (
          <p className="text-[13px]" style={{ color: "var(--paper-40)" }} lang={language}>
            {copy.thinking}
          </p>
        )}

        {error && (
          <p className="text-[13px]" style={{ color: "var(--color-caution)" }}>
            {error}
          </p>
        )}
      </div>

      {canListen ? (
        <button
          type="button"
          onClick={toggleListening}
          disabled={thinking}
          className="flex items-center justify-center gap-3 rounded-xl px-4 py-3.5 text-sm transition-colors disabled:opacity-50"
          style={{
            border: `1px solid ${listening ? "var(--color-accent)" : "var(--paper-20)"}`,
            background: listening ? "var(--paper-08)" : "transparent",
            color: "var(--color-paper)",
          }}
          lang={language}
        >
          <MicIcon size={17} strokeWidth={1.5} />
          {listening ? copy.listeningLabel : copy.askLabel}
        </button>
      ) : (
        // No on-device recognition in this browser. Typing is the fallback,
        // not a dead end.
        <form
          onSubmit={(event) => {
            event.preventDefault();
            void ask(draft);
          }}
          className="flex gap-2"
        >
          <input
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            placeholder={copy.askPlaceholder}
            aria-label={copy.askLabel}
            lang={language}
            className="min-w-0 flex-1 rounded-xl px-3.5 py-3 text-sm outline-none"
            style={{
              border: "1px solid var(--paper-20)",
              background: "var(--paper-05)",
              color: "var(--color-paper)",
            }}
          />
          <button
            type="submit"
            disabled={thinking || !draft.trim()}
            className="rounded-xl px-4 text-sm font-medium disabled:opacity-40"
            style={{ background: "var(--color-accent)", color: "var(--color-paper)" }}
            lang={language}
          >
            {copy.send}
          </button>
        </form>
      )}
    </aside>
  );
}
