/**
 * Typed client for the FastAPI backend.
 *
 * Errors carry the backend's own `detail` string, because those strings are
 * written to be read by a person ("That recording is too long. Try a shorter
 * one.") rather than by a developer. Screens surface them directly.
 */

import type {
  AssistantQueryResponse,
  ExtractResponse,
  HealthResponse,
  Language,
  MatchResponse,
  NormalizeResponse,
  SchemeDetail,
  SchemeSummary,
  PassportResponse,
  SessionSummary,
  SkillEdit,
  SynthesizeResponse,
  TranscribeResponse,
} from "./types";

export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") ??
  "http://localhost:8000";

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }

  /** True when the server is up but a provider is not configured. */
  get isUnavailable(): boolean {
    return this.status === 503;
  }

  get isRateLimited(): boolean {
    return this.status === 429;
  }
}

async function request<T>(
  path: string,
  init: RequestInit = {},
  sessionId?: string | null,
): Promise<T> {
  const headers = new Headers(init.headers);
  if (!(init.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
  // The rate limiter keys on this before falling back to IP, so shared
  // connections do not throttle each other.
  if (sessionId) headers.set("X-VoicePath-Session", sessionId);

  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, { ...init, headers });
  } catch {
    throw new ApiError(
      "Could not reach VoicePath. Check that the backend is running.",
      0,
    );
  }

  if (!response.ok) {
    let detail = `Request failed (${response.status})`;
    try {
      const body = (await response.json()) as { detail?: unknown };
      if (typeof body.detail === "string") detail = body.detail;
      else if (Array.isArray(body.detail)) detail = "That input was not valid.";
    } catch {
      /* Non-JSON error body; the generic message stands. */
    }
    throw new ApiError(detail, response.status);
  }

  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export const api = {
  health: () => request<HealthResponse>("/health"),

  transcribe: (audio: Blob, language: LanguageParam) => {
    const form = new FormData();
    // Name the part for what the blob actually is: the backend forwards both
    // filename and content type to Sarvam, which validates the type and
    // rejects anything in the WebM family.
    const filename = audio.type.includes("wav") ? "speech.wav" : "speech.webm";
    form.append("file", audio, filename);
    form.append("language", language);
    return request<TranscribeResponse>("/api/speech/transcribe", {
      method: "POST",
      body: form,
    });
  },

  clientTranscript: (transcript: string, languageDetected: string) =>
    request<TranscribeResponse>("/api/speech/client-transcript", {
      method: "POST",
      body: JSON.stringify({
        transcript,
        language_detected: languageDetected,
      }),
    }),

  synthesize: (text: string, language: Language) =>
    request<SynthesizeResponse>("/api/speech/synthesize", {
      method: "POST",
      body: JSON.stringify({ text, language }),
    }),

  extract: (sessionId: string) =>
    request<ExtractResponse>(
      "/api/profile/extract",
      { method: "POST", body: JSON.stringify({ session_id: sessionId }) },
      sessionId,
    ),

  normalize: (sessionId: string, skills: SkillEdit[]) =>
    request<NormalizeResponse>(
      "/api/profile/normalize",
      {
        method: "POST",
        body: JSON.stringify({ session_id: sessionId, skills }),
      },
      sessionId,
    ),

  // `language` is the one being read, which is not always the one that was
  // spoken: explanations are generated per request, so a language switch has
  // to re-ask rather than re-render.
  match: (sessionId: string, language: Language) =>
    request<MatchResponse>(
      "/api/schemes/match",
      {
        method: "POST",
        body: JSON.stringify({ session_id: sessionId, language }),
      },
      sessionId,
    ),

  schemes: (district?: string) =>
    request<SchemeSummary[]>(
      `/api/schemes${district ? `?district=${encodeURIComponent(district)}` : ""}`,
    ),

  scheme: (id: number) =>
    request<SchemeDetail>(`/api/schemes/${id}`),

  storedMatch: (id: number, sessionId: string) =>
    request<import("./types").MatchResult>(
      `/api/schemes/${id}/match/${sessionId}`,
    ),

  ask: (params: {
    sessionId: string | null;
    schemeId: number | null;
    question: string;
    language: Language;
  }) =>
    request<AssistantQueryResponse>(
      "/api/assistant/query",
      {
        method: "POST",
        body: JSON.stringify({
          session_id: params.sessionId,
          scheme_id: params.schemeId,
          question_text: params.question,
          language: params.language,
        }),
      },
      params.sessionId,
    ),

  passport: (sessionId: string) =>
    request<PassportResponse>(`/api/sessions/${sessionId}`, {}, sessionId),

  setAudioRetention: (sessionId: string, retained: boolean) =>
    request<SessionSummary>(
      `/api/sessions/${sessionId}/audio-retention`,
      { method: "POST", body: JSON.stringify({ audio_retained: retained }) },
      sessionId,
    ),
};

type LanguageParam = Language | "auto";
