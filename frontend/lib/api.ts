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
  ExtractedProfile,
  HealthResponse,
  KnownPlace,
  Language,
  MatchResponse,
  NearbyCategory,
  NearbyResponse,
  NormalizeResponse,
  SchemeDetail,
  SchemeSummary,
  PassportResponse,
  QueryUnderstandResponse,
  SkillEdit,
  SupportResponse,
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

/*
 * Session keys (2026-11-05).
 *
 * A session opens only with its secret key: the API hands it out once, when
 * the session is created, and refuses any request about that session that
 * does not send it back in X-VoicePath-Session-Key. The id alone -- which is in
 * request paths, so in server logs -- opens nothing.
 *
 * Kept here rather than in React state so it is in place the instant the
 * session exists: the screen that created a session may ask about it before
 * any effect has run. Mirrored to sessionStorage (this tab only, like the
 * session itself) so a reload keeps working. Never put in a URL.
 */
const KEYS_STORAGE = "voicepath.session-keys.v1";
const KEYS_KEPT = 5;
const sessionKeys = new Map<string, string>();

function storedKeys(): Record<string, string> {
  try {
    const raw = window.sessionStorage.getItem(KEYS_STORAGE);
    const parsed = raw ? (JSON.parse(raw) as unknown) : null;
    return parsed && typeof parsed === "object" ? (parsed as Record<string, string>) : {};
  } catch {
    return {};
  }
}

function rememberSessionKey(sessionId: string | null | undefined, key: string | null | undefined) {
  if (!sessionId || !key) return;
  sessionKeys.set(sessionId, key);
  try {
    const kept = Object.entries({ ...storedKeys(), [sessionId]: key }).slice(-KEYS_KEPT);
    window.sessionStorage.setItem(KEYS_STORAGE, JSON.stringify(Object.fromEntries(kept)));
  } catch {
    /* Private mode, or storage full: the key still works until a reload. */
  }
}

function keyFor(sessionId: string): string | undefined {
  const held = sessionKeys.get(sessionId);
  if (held) return held;
  if (typeof window === "undefined") return undefined;
  const stored = storedKeys()[sessionId];
  if (stored) sessionKeys.set(sessionId, stored);
  return stored;
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
  if (sessionId) {
    headers.set("X-VoicePath-Session", sessionId);
    const key = keyFor(sessionId);
    if (key) headers.set("X-VoicePath-Session-Key", key);
  }

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
    }).then((result) => {
      rememberSessionKey(result.session_id, result.session_key);
      return result;
    });
  },

  clientTranscript: (transcript: string, languageDetected: string) =>
    request<TranscribeResponse>("/api/speech/client-transcript", {
      method: "POST",
      body: JSON.stringify({
        transcript,
        language_detected: languageDetected,
      }),
    }).then((result) => {
      rememberSessionKey(result.session_id, result.session_key);
      return result;
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

  /**
   * The stored match, with its reasons written in the language being read.
   *
   * The scores come back untouched -- they are the audited numbers. Only the
   * sentences are rewritten, and only when the stored ones are in another
   * language.
   */
  storedMatch: (id: number, sessionId: string, language: Language) =>
    request<import("./types").MatchResult>(
      `/api/schemes/${id}/match/${sessionId}?language=${language}`,
      {},
      sessionId,
    ),

  /**
   * Work typed on the understanding screen.
   *
   * Goes through extraction, exactly as speech does, rather than straight to
   * normalization -- which would answer "which skill is this nearest?" for any
   * text at all, and did: football players scored 0.75 against the taxonomy
   * and became an uncertain skill card.
   */
  addTypedSkill: (sessionId: string, text: string, language: Language) =>
    request<import("./types").AddSkillResponse>(
      "/api/profile/skills",
      {
        method: "POST",
        body: JSON.stringify({ session_id: sessionId, text, language }),
      },
      sessionId,
    ),

  /** Years of work, corrected by the person. Null clears it. */
  correctExperience: (sessionId: string, experienceYears: number | null) =>
    request<ExtractedProfile>(
      "/api/profile/experience",
      {
        method: "PUT",
        body: JSON.stringify({
          session_id: sessionId,
          experience_years: experienceYears,
        }),
      },
      sessionId,
    ),

  /** What was this person doing -- describing work, asking, or both. */
  understand: (text: string, language: Language) =>
    request<QueryUnderstandResponse>("/api/query/understand", {
      method: "POST",
      body: JSON.stringify({ text, language }),
    }),

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

  /**
   * Where the map centres, and the openings by town.
   *
   * Answered from the catalogue alone, so it is quick. A device location is
   * sent in the body, never the URL -- query strings land in access logs --
   * and is already coarsened by `coarsen` before it gets here.
   */
  nearby: (params: {
    place?: string | null;
    latitude?: number | null;
    longitude?: number | null;
  }) =>
    request<NearbyResponse>("/api/places/nearby", {
      method: "POST",
      body: JSON.stringify(params),
    }),

  /** Offices near a point, from OpenStreetMap. Can be slow; ask separately. */
  support: (params: {
    latitude: number;
    longitude: number;
    radiusKm: number;
    categories: NearbyCategory[];
  }) =>
    request<SupportResponse>("/api/places/support", {
      method: "POST",
      body: JSON.stringify({
        latitude: params.latitude,
        longitude: params.longitude,
        radius_km: params.radiusKm,
        categories: params.categories,
      }),
    }),

  knownPlaces: () => request<KnownPlace[]>("/api/places/known"),

  passport: (sessionId: string) =>
    request<PassportResponse>(`/api/sessions/${sessionId}`, {}, sessionId),
};

type LanguageParam = Language | "auto";
