/**
 * On-device speech, used when the server-side providers are not configured.
 *
 * This is a real fallback, not a placeholder: the Web Speech API does actual
 * recognition and synthesis on the device, and it supports ta-IN, hi-IN and
 * en-IN. In this mode the audio never leaves the browser at all, which is
 * stricter than the default path rather than looser.
 *
 * Support is uneven -- Chrome and Edge have recognition, Firefox does not --
 * so every entry point here reports capability rather than assuming it.
 */

import { localeFor } from "./i18n";
import type { Language } from "./types";

/* The Web Speech API is not in TypeScript's DOM lib. Only the parts used. */

interface SpeechRecognitionAlternativeLike {
  transcript: string;
  confidence: number;
}

interface SpeechRecognitionResultLike {
  readonly length: number;
  isFinal: boolean;
  [index: number]: SpeechRecognitionAlternativeLike;
}

interface SpeechRecognitionResultListLike {
  readonly length: number;
  [index: number]: SpeechRecognitionResultLike;
}

interface SpeechRecognitionEventLike extends Event {
  resultIndex: number;
  results: SpeechRecognitionResultListLike;
}

interface SpeechRecognitionErrorEventLike extends Event {
  error: string;
}

interface SpeechRecognitionLike extends EventTarget {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  maxAlternatives: number;
  start(): void;
  stop(): void;
  abort(): void;
  onresult: ((event: SpeechRecognitionEventLike) => void) | null;
  onerror: ((event: SpeechRecognitionErrorEventLike) => void) | null;
  onend: (() => void) | null;
}

type SpeechRecognitionConstructor = new () => SpeechRecognitionLike;

function recognitionConstructor(): SpeechRecognitionConstructor | null {
  if (typeof window === "undefined") return null;
  const w = window as unknown as {
    SpeechRecognition?: SpeechRecognitionConstructor;
    webkitSpeechRecognition?: SpeechRecognitionConstructor;
  };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null;
}

export function canRecogniseOnDevice(): boolean {
  return recognitionConstructor() !== null;
}

export function canSynthesiseOnDevice(): boolean {
  return typeof window !== "undefined" && "speechSynthesis" in window;
}

export interface RecognitionHandle {
  stop(): void;
  abort(): void;
}

export interface RecognitionCallbacks {
  /** Fires as words arrive. `isFinal` marks a settled segment. */
  onPartial(text: string, isFinal: boolean): void;
  onError(reason: "not-allowed" | "no-speech" | "unsupported" | "other"): void;
  onEnd(finalTranscript: string): void;
}

/**
 * Start on-device recognition.
 *
 * Final segments accumulate into one transcript; interim text is shown but
 * never kept, so a half-heard phrase cannot end up in the record.
 */
export function startRecognition(
  language: Language,
  callbacks: RecognitionCallbacks,
): RecognitionHandle | null {
  const Constructor = recognitionConstructor();
  if (!Constructor) {
    callbacks.onError("unsupported");
    return null;
  }

  const recognition = new Constructor();
  recognition.lang = localeFor(language);
  recognition.continuous = true;
  recognition.interimResults = true;
  recognition.maxAlternatives = 1;

  let settled = "";
  let stoppedByUser = false;

  recognition.onresult = (event) => {
    let interim = "";
    for (let i = event.resultIndex; i < event.results.length; i += 1) {
      const result = event.results[i];
      if (!result) continue;
      const alternative = result[0];
      if (!alternative) continue;
      if (result.isFinal) {
        settled += (settled ? " " : "") + alternative.transcript.trim();
      } else {
        interim += alternative.transcript;
      }
    }
    const shown = (settled + (interim ? ` ${interim}` : "")).trim();
    callbacks.onPartial(shown, interim === "");
  };

  recognition.onerror = (event) => {
    if (event.error === "not-allowed" || event.error === "service-not-allowed") {
      callbacks.onError("not-allowed");
    } else if (event.error === "no-speech") {
      callbacks.onError("no-speech");
    } else if (event.error !== "aborted") {
      callbacks.onError("other");
    }
  };

  recognition.onend = () => {
    // Chrome ends the session on a pause. Restart unless the person is done,
    // so a thinking pause does not cut someone off mid-story.
    if (!stoppedByUser) {
      try {
        recognition.start();
        return;
      } catch {
        /* Already ended for good. */
      }
    }
    callbacks.onEnd(settled.trim());
  };

  try {
    recognition.start();
  } catch {
    callbacks.onError("other");
    return null;
  }

  return {
    stop() {
      stoppedByUser = true;
      recognition.stop();
    },
    abort() {
      stoppedByUser = true;
      recognition.abort();
    },
  };
}

/** Speak text on-device. Resolves when speech finishes or cannot start. */
export function speakOnDevice(text: string, language: Language): Promise<void> {
  return new Promise((resolve) => {
    if (!canSynthesiseOnDevice() || !text.trim()) {
      resolve();
      return;
    }
    const synth = window.speechSynthesis;
    synth.cancel();

    const utterance = new SpeechSynthesisUtterance(text);
    const locale = localeFor(language);
    utterance.lang = locale;
    utterance.rate = 0.95;

    // Prefer a voice that actually speaks the language; falling back to the
    // browser default would read Tamil with an English voice.
    const voice =
      synth.getVoices().find((v) => v.lang === locale) ??
      synth.getVoices().find((v) => v.lang.startsWith(language));
    if (voice) utterance.voice = voice;

    utterance.onend = () => resolve();
    utterance.onerror = () => resolve();
    synth.speak(utterance);
  });
}

export function stopSpeaking(): void {
  if (canSynthesiseOnDevice()) window.speechSynthesis.cancel();
}

/** Play base64 WAV from the TTS endpoint. */
export function playBase64Audio(base64: string): Promise<void> {
  return new Promise((resolve) => {
    const audio = new Audio(`data:audio/wav;base64,${base64}`);
    audio.onended = () => resolve();
    audio.onerror = () => resolve();
    void audio.play().catch(() => resolve());
  });
}
