/**
 * WebM/Opus to WAV, in the browser.
 *
 * MediaRecorder gives us whatever container the browser prefers -- WebM/Opus in
 * Chrome and Firefox, MP4/AAC in Safari -- and Sarvam accepts none of the WebM
 * family. Rather than transcode server-side (an ffmpeg dependency for one
 * format change) the recording is decoded and re-encoded here, where the audio
 * already lives.
 *
 * Output is 16 kHz mono 16-bit PCM: the rate speech recognition actually uses,
 * and the one that keeps an uncompressed upload small. A minute of speech is
 * about 1.9 MB against the API's 15 MB ceiling, so roughly eight minutes fit.
 */

/** Speech models are trained at 16 kHz; sending more is bytes, not accuracy. */
const TARGET_SAMPLE_RATE = 16000;
const BYTES_PER_SAMPLE = 2;
const WAV_HEADER_BYTES = 44;

type AudioContextConstructor = new (
  options?: AudioContextOptions,
) => AudioContext;

function audioContextConstructor(): AudioContextConstructor | null {
  if (typeof window === "undefined") return null;
  const w = window as unknown as {
    AudioContext?: AudioContextConstructor;
    webkitAudioContext?: AudioContextConstructor;
  };
  return w.AudioContext ?? w.webkitAudioContext ?? null;
}

export function canConvertToWav(): boolean {
  return (
    audioContextConstructor() !== null &&
    typeof window !== "undefined" &&
    typeof window.OfflineAudioContext !== "undefined"
  );
}

/**
 * Decode a recorded blob and re-encode it as WAV.
 *
 * Throws if the browser cannot decode the container. The caller decides what
 * that means -- this module does not invent silence to paper over a failure.
 */
export async function toWav(recording: Blob): Promise<Blob> {
  const Constructor = audioContextConstructor();
  if (!Constructor) throw new Error("No AudioContext to decode with");

  const bytes = await recording.arrayBuffer();
  const context = new Constructor();
  let decoded: AudioBuffer;
  try {
    // decodeAudioData detaches the buffer it is handed, so it gets a copy --
    // otherwise a retry would find an empty ArrayBuffer.
    decoded = await context.decodeAudioData(bytes.slice(0));
  } finally {
    void context.close().catch(() => undefined);
  }

  return encodeWav(await downmixTo16k(decoded));
}

/**
 * Resample to 16 kHz and fold to one channel.
 *
 * Connecting a multi-channel buffer to a mono destination makes the Web Audio
 * graph do the downmix, which is both correct and faster than averaging by hand.
 */
async function downmixTo16k(buffer: AudioBuffer): Promise<Float32Array> {
  const frames = Math.max(
    1,
    Math.ceil(buffer.duration * TARGET_SAMPLE_RATE),
  );
  const offline = new OfflineAudioContext(1, frames, TARGET_SAMPLE_RATE);
  const source = offline.createBufferSource();
  source.buffer = buffer;
  source.connect(offline.destination);
  source.start();
  const rendered = await offline.startRendering();
  return rendered.getChannelData(0);
}

function encodeWav(samples: Float32Array): Blob {
  const dataBytes = samples.length * BYTES_PER_SAMPLE;
  const view = new DataView(new ArrayBuffer(WAV_HEADER_BYTES + dataBytes));

  writeAscii(view, 0, "RIFF");
  view.setUint32(4, 36 + dataBytes, true);
  writeAscii(view, 8, "WAVE");

  writeAscii(view, 12, "fmt ");
  view.setUint32(16, 16, true); // PCM header length
  view.setUint16(20, 1, true); // format: uncompressed PCM
  view.setUint16(22, 1, true); // channels
  view.setUint32(24, TARGET_SAMPLE_RATE, true);
  view.setUint32(28, TARGET_SAMPLE_RATE * BYTES_PER_SAMPLE, true); // byte rate
  view.setUint16(32, BYTES_PER_SAMPLE, true); // block align
  view.setUint16(34, 8 * BYTES_PER_SAMPLE, true); // bits per sample

  writeAscii(view, 36, "data");
  view.setUint32(40, dataBytes, true);

  let offset = WAV_HEADER_BYTES;
  for (let i = 0; i < samples.length; i += 1) {
    // Clamp before scaling: a sample above 1.0 would wrap to full-scale
    // negative and turn a loud moment into a click.
    const sample = Math.max(-1, Math.min(1, samples[i] ?? 0));
    view.setInt16(offset, sample < 0 ? sample * 0x8000 : sample * 0x7fff, true);
    offset += BYTES_PER_SAMPLE;
  }

  return new Blob([view.buffer], { type: "audio/wav" });
}

function writeAscii(view: DataView, offset: number, text: string): void {
  for (let i = 0; i < text.length; i += 1) {
    view.setUint8(offset + i, text.charCodeAt(i));
  }
}
