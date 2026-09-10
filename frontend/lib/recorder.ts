/**
 * Microphone capture and live amplitude (PRD sections 2 and 4.1).
 *
 * Two jobs, and the PRD is explicit that they are separate steps: produce an
 * audio blob, and expose the live level so the waveform reacts to the person's
 * actual voice rather than animating on a timer.
 *
 * The stream's tracks are stopped on every exit path, including errors. A live
 * MediaStream leaves the browser's recording indicator on, which on a screen
 * that promises "your voice is not saved" would be its own kind of lie.
 */

import { toWav } from "./wav";

export type RecorderError = "denied" | "unsupported" | "other";

export interface Recorder {
  /** Per-band levels in [0, 1], newest read. `bands` entries for the waveform. */
  levels(bands: number): number[];
  /** Overall loudness in [0, 1]. */
  level(): number;
  /**
   * Stop, release the microphone, and resolve with the recording as WAV.
   * Converted here because Sarvam rejects the WebM/Opus MediaRecorder produces.
   */
  stop(): Promise<Blob | null>;
  /** Stop and release without producing a blob. */
  cancel(): void;
  readonly mimeType: string;
}

export function isRecordingSupported(): boolean {
  return (
    typeof navigator !== "undefined" &&
    typeof navigator.mediaDevices?.getUserMedia === "function" &&
    typeof window !== "undefined" &&
    typeof window.MediaRecorder !== "undefined"
  );
}

function pickMimeType(): string {
  const candidates = [
    "audio/webm;codecs=opus",
    "audio/webm",
    "audio/ogg;codecs=opus",
    "audio/mp4",
  ];
  for (const type of candidates) {
    if (MediaRecorder.isTypeSupported(type)) return type;
  }
  return "";
}

export async function startRecording(): Promise<Recorder> {
  if (!isRecordingSupported()) {
    throw Object.assign(new Error("Recording is not supported"), {
      reason: "unsupported" as RecorderError,
    });
  }

  let stream: MediaStream;
  try {
    stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
      },
    });
  } catch (error) {
    const denied =
      error instanceof DOMException &&
      (error.name === "NotAllowedError" || error.name === "SecurityError");
    throw Object.assign(new Error("Microphone unavailable"), {
      reason: (denied ? "denied" : "other") as RecorderError,
    });
  }

  const context = new AudioContext();
  const source = context.createMediaStreamSource(stream);
  const analyser = context.createAnalyser();
  // 512 bins is enough resolution for a 48-bar waveform and cheap enough to
  // read every animation frame.
  analyser.fftSize = 1024;
  analyser.smoothingTimeConstant = 0.72;
  source.connect(analyser);

  const spectrum = new Uint8Array(analyser.frequencyBinCount);
  const waveform = new Uint8Array(analyser.fftSize);

  const mimeType = pickMimeType();
  const recorder = new MediaRecorder(
    stream,
    mimeType ? { mimeType } : undefined,
  );
  const chunks: Blob[] = [];
  recorder.ondataavailable = (event) => {
    if (event.data.size > 0) chunks.push(event.data);
  };
  recorder.start(250);

  let released = false;
  const release = () => {
    if (released) return;
    released = true;
    stream.getTracks().forEach((track) => track.stop());
    void context.close().catch(() => undefined);
  };

  return {
    mimeType: recorder.mimeType || mimeType || "audio/webm",

    levels(bands: number): number[] {
      if (released || bands <= 0) return new Array(Math.max(bands, 0)).fill(0);
      analyser.getByteFrequencyData(spectrum);

      // Human speech energy sits low in the spectrum, so a linear split across
      // all bins would leave most bars flat. Sampling logarithmically spreads
      // the voice across the whole width.
      const out: number[] = [];
      const bins = spectrum.length;
      for (let i = 0; i < bands; i += 1) {
        const from = Math.floor(bins ** (i / bands)) - 1;
        const to = Math.max(from + 1, Math.floor(bins ** ((i + 1) / bands)) - 1);
        let peak = 0;
        for (let bin = Math.max(0, from); bin < Math.min(bins, to); bin += 1) {
          const value = spectrum[bin] ?? 0;
          if (value > peak) peak = value;
        }
        out.push(Math.min(1, peak / 255));
      }
      return out;
    },

    level(): number {
      if (released) return 0;
      analyser.getByteTimeDomainData(waveform);
      let sum = 0;
      for (let i = 0; i < waveform.length; i += 1) {
        const centred = ((waveform[i] ?? 128) - 128) / 128;
        sum += centred * centred;
      }
      // RMS, then a gain that puts ordinary speech in the upper half of the
      // range without clipping a loud room to a flat line.
      return Math.min(1, Math.sqrt(sum / waveform.length) * 3.2);
    },

    async stop(): Promise<Blob | null> {
      if (released) return null;
      const finished = new Promise<Blob | null>((resolve) => {
        recorder.onstop = () => {
          resolve(
            chunks.length
              ? new Blob(chunks, { type: recorder.mimeType || "audio/webm" })
              : null,
          );
        };
      });
      try {
        if (recorder.state !== "inactive") recorder.stop();
        else return null;
      } finally {
        // Release after stop() so the last chunk still flushes.
        setTimeout(release, 0);
      }

      const captured = await finished;
      if (!captured) return null;
      return toWav(captured);
    },

    cancel(): void {
      try {
        if (recorder.state !== "inactive") recorder.stop();
      } catch {
        /* Already stopped. */
      }
      release();
    },
  };
}
