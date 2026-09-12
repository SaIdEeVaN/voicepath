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
  stopAllSpeech,
  type RecognitionHandle,
} from "@/lib/browser-speech";
import { copyFor } from "@/lib/i18n";
import { useSession } from "@/lib/session";
import type { Citation, Language } from "@/lib/types";

interface Exchange {
  question: string;
  answer: string;
  sourceNote: string;
  fromData: boolean;
  /** Empty unless the answer came from the published guidelines. */
  citations: Citation[];
  /**
   * The language this exchange happened in.
   *
   * Past answers are not re-translated when the reader switches language:
   * this is a record of a conversation, and silently rewriting what was
   * already said is worse than leaving it. But the markup must still be
   * honest -- tagging Tamil prose as `hi` picks the wrong font and makes a
   * screen reader mispronounce it -- so each line carries its own tag.
   */
  askedIn: Language;
}

export function AskVoicePath({ schemeId }: { schemeId: number }) {
  const { language, sessionId } = useSession();
  const copy = copyFor(language);

  const [exchanges, setExchanges] = useState<Exchange[]>([]);
  const [listening, setListening] = useState(false);
  const [thinking, setThinking] = useState(false);
  const [draft, setDraft] = useState("");
  const [error, setError] = useState<string | null>(null);

  const recognitionRef = useRef<RecognitionHandle | null>(null);
  // Synthesis is awaited outside the render lifecycle, so it can resolve
  // after the screen is gone. Without this the clip starts playing to a
  // page the person already left -- the cleanup ran before the audio existed.
  const mounted = useRef(true);
  const canListen = canRecogniseOnDevice();

  useEffect(
    () => () => {
      mounted.current = false;
      recognitionRef.current?.abort();
      stopAllSpeech();
    },
    [],
  );

  // TODO: RAG integration. This asks about one scheme, and the backend
  // answers from that row alone -- deliberately, so it cannot invent an
  // eligibility rule. Questions about the scheme itself ("do I qualify if
  // my income is above the limit?") need the published guidelines, which
  // the retrieval layer on the `rag` branch answers with a citation.
  // Route there when a question is not about this listing.
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
          schemeId,
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
            citations: result.citations ?? [],
            askedIn: language as Language,
          },
        ]);

        // The answer is on screen now, so stop saying "thinking". Speech is
        // deliberately not awaited here: synthesis can take seconds, and
        // holding the spinner until the audio finishes made a delivered answer
        // look like a stalled one.
        setThinking(false);

        // Server TTS when configured, on-device otherwise -- both are real
        // speech, so the answer is heard either way.
        void (async () => {
          try {
            const speech = await api.synthesize(
              result.answer_text,
              language as Language,
            );
            if (!mounted.current) return;
            if (speech.audio_base64) await playBase64Audio(speech.audio_base64);
            else if (speech.use_browser_tts) {
              await speakOnDevice(result.answer_text, language as Language);
            }
          } catch {
            if (!mounted.current) return;
            await speakOnDevice(result.answer_text, language as Language);
          }
        })();
      } catch (cause) {
        setError(
          cause instanceof ApiError ? cause.message : copy.somethingWentWrong,
        );
        setThinking(false);
      }
    },
    [language, schemeId, sessionId],
  );

  const toggleListening = useCallback(() => {
    if (listening) {
      recognitionRef.current?.stop();
      recognitionRef.current = null;
      setListening(false);
      return;
    }
    if (!canListen) return;

    stopAllSpeech();
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
              lang={exchange.askedIn}
            >
              {exchange.question}
            </p>
            <p
              className="max-w-[92%] self-start rounded-[14px_14px_14px_4px] px-4 py-3 text-[14.5px] leading-relaxed"
              style={{ background: "var(--paper-05)" }}
              lang={exchange.askedIn}
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
              lang={exchange.askedIn}
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

            {/* What the answer was drawn from. The point of retrieval here is
                not that the machine sounds authoritative -- it is that the
                person can go and read the paragraph themselves. A claim about
                eligibility with no traceable source is the thing this is
                built to avoid. */}
            {exchange.citations.length > 0 && (
              <ul className="mt-2 flex flex-col gap-1.5">
                {exchange.citations.map((citation, index) => (
                  <li
                    key={`${citation.source}-${index}`}
                    className="rounded-lg px-3 py-2 text-[12px] leading-relaxed"
                    style={{ background: "var(--ink-04)", color: "var(--ink-55)" }}
                  >
                    <span className="font-mono text-[11px]" style={{ color: "var(--ink-45)" }}>
                      {citation.document_title}
                      {citation.heading ? ` · ${citation.heading}` : ""}
                    </span>
                    <span className="mt-1 block">&ldquo;{citation.excerpt}&rdquo;</span>
                    {citation.source_url && (
                      <a
                        href={citation.source_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="mt-1.5 inline-block underline underline-offset-4"
                        style={{ color: "var(--color-accent)" }}
                        lang={language}
                      >
                        {copy.readOnGovPage} ↗
                      </a>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </div>
        ))}

        {/* While listening, the words appear in the field below rather than
            in a bubble here. Two copies of the same in-progress sentence, one
            of them editable, is confusing about which one is real. */}

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

      {/* One field, both ways in.
      
          This used to be either/or: the microphone when the browser could
          listen, the text box only when it could not. So in Chrome there was
          no way to type at all -- which fails a noisy room, a quiet room, a
          shared phone, and anyone who would rather write than speak.
      
          Speaking still sends as soon as the sentence ends. The words appear
          in the field as they are recognised, so a mishearing is visible, but
          asking is not made to wait for a second tap: this product is used by
          people who may not read the button they would have to find. */}
      <form
        onSubmit={(event) => {
          event.preventDefault();
          void ask(draft);
        }}
        className="flex gap-2"
      >
        <div
          className="flex min-w-0 flex-1 items-center gap-1.5 rounded-xl pr-1.5"
          style={{
            border: `1px solid ${listening ? "var(--color-accent)" : "var(--paper-20)"}`,
            background: listening ? "var(--paper-08)" : "var(--paper-05)",
          }}
        >
          <input
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            placeholder={listening ? copy.listeningLabel : copy.askPlaceholder}
            aria-label={copy.askLabel}
            disabled={thinking}
            lang={language}
            className="min-w-0 flex-1 bg-transparent px-3.5 py-3 text-sm outline-none disabled:opacity-50"
            style={{ color: "var(--color-paper)" }}
          />

          {canListen && (
            <button
              type="button"
              onClick={toggleListening}
              disabled={thinking}
              aria-pressed={listening}
              aria-label={listening ? copy.listeningLabel : copy.askLabel}
              title={listening ? copy.listeningLabel : copy.askLabel}
              className="grid h-9 w-9 flex-none place-items-center rounded-lg transition-colors disabled:opacity-50"
              style={{
                background: listening ? "var(--color-accent)" : "var(--paper-08)",
                color: "var(--color-paper)",
              }}
            >
              <MicIcon size={17} strokeWidth={1.5} />
            </button>
          )}
        </div>

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
    </aside>
  );
}
