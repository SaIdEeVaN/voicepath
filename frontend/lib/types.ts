/**
 * Wire types. These mirror `backend/app/models/schemas.py` exactly -- if you
 * change one, change the other.
 */

export type Language = "ta" | "hi" | "en";

export interface SkillCandidate {
  id: number;
  code: string;
  name: string;
  category: string;
  hint: string | null;
  similarity: number;
  /** {"en": ..., "ta": ..., "hi": ...}. Use `skillLabel` to read it. */
  display_names: Record<string, string>;
}

export interface ExtractedSkill {
  id: string | null;
  raw_name: string;
  evidence_phrase: string;
  normalized_skill_id: number | null;
  normalized_code: string | null;
  normalized_name: string | null;
  display_names: Record<string, string>;
  category: string | null;
  match_confidence: number | null;
  needs_disambiguation: boolean;
  candidates: SkillCandidate[];
  user_confirmed: boolean;
}

export interface ExtractedProfile {
  id: string | null;
  session_id: string | null;
  experience_years: number | null;
  experience_context: string | null;
  education: string[];
  certifications: string[];
  location: string | null;
  work_preferences: string[];
  uncertainty_flags: string[];
}

export interface TranscribeResponse {
  session_id: string;
  transcript: string;
  language_detected: string;
  provider: string;
  audio_retained: boolean;
}

export interface SynthesizeResponse {
  provider: string;
  audio_base64: string | null;
  speech_locale: string;
  use_browser_tts: boolean;
}

export interface ExtractResponse {
  session_id: string | null;
  profile: ExtractedProfile;
  skills: ExtractedSkill[];
  provider: string;
  degraded: boolean;
}

export interface SkillEdit {
  id?: string | null;
  raw_name: string;
  evidence_phrase: string;
  removed?: boolean;
  chosen_skill_id?: number | null;
}

export interface NormalizeResponse {
  session_id: string | null;
  skills: ExtractedSkill[];
  provider: string;
  degraded: boolean;
}

export interface SchemeSummary {
  id: number;
  title: string;
  organization: string;
  location: string;
  district: string | null;
  type: string;
  minimum_experience: number;
  certifications_required: string[];
  salary_min: number | null;
  salary_max: number | null;
  nsqf_level: string | null;
  source_reference: string | null;
  /** The government's own page for this scheme. Shown as a link, never guessed. */
  official_url: string | null;
}

export interface SchemeDetail extends SchemeSummary {
  /** Admin views only. A deactivated scheme is matched to nobody. */
  is_active?: boolean;
  description: string | null;
  required_skills: SkillCandidate[];
}

export interface ScoreBreakdown {
  skill_similarity_score: number;
  experience_score: number;
  eligibility_score: number;
  location_score: number;
}

export interface MatchResult {
  scheme: SchemeSummary;
  rank: number;
  overall_score: number;
  breakdown: ScoreBreakdown;
  explanation_text: string | null;
  explanation_bullets: string[];
  matched_skill_codes: string[];
  skill_evidence?: boolean;
}

export interface MatchResponse {
  session_id: string | null;
  matches: MatchResult[];
  explanation_provider: string;
  degraded: boolean;
}

export interface QueryUnderstandResponse {
  describes_work: boolean;
  asks_question: boolean;
  /** Their words, never a rephrasing. Null when they asked nothing. */
  question: string | null;
  provider: string;
  /** They said someone is in danger. Ask the assistant; it answers with 112. */
  urgent?: boolean;
}

export interface Citation {
  source: string;
  /**
   * The government's own page for this document, when one has been recorded.
   *
   * Often null, and that is the honest state: no URL is ever constructed to
   * fill the gap, so a document nobody has recorded a page for cites its name
   * alone.
   */
  source_url: string | null;
  document_title: string;
  heading: string | null;
  excerpt: string;
  similarity: number;
}

export interface AssistantQueryResponse {
  question_text: string;
  answer_text: string;
  source_note: string;
  provider: string;
  answered_from_data: boolean;
  /** Present only when the answer came from a scheme document. */
  citations?: Citation[];
  /** The answer is the emergency numbers; show SafetyNotice, not a reply. */
  urgent?: boolean;
}

export interface SessionSummary {
  id: string;
  created_at: string;
  language_detected: string | null;
  transcript: string | null;
  audio_retained: boolean;
  audio_url: string | null;
}

export interface PassportResponse {
  session: SessionSummary;
  profile: ExtractedProfile | null;
  skills: ExtractedSkill[];
}

export interface HealthResponse {
  status: "ok" | "degraded";
  providers: Record<string, string>;
  degraded: string[];
  database: Record<string, unknown>;
  /**
   * "ok", "offline" (no model configured), or why a configured one is not
   * answering -- "rate_limited", "daily_limit", "quota", "rejected",
   * "model_missing", "server_error", "unreachable" -- with when it should
   * be back. Absent from a backend older than this field.
   */
  llm?: { status: string; since?: string; until?: string };
}

/** What typed text on the understanding screen turned out to be. */
export interface AddSkillResponse {
  accepted: boolean;
  kind: "work" | "question" | "neither";
  skills: ExtractedSkill[];
  question: string | null;
  provider: string;
  /** The text said someone is in danger; kind is then "question". */
  urgent?: boolean;
}

/* -- Near you (the map) -------------------------------------------------- */

export type NearbyCategory = "training" | "employment" | "government" | "bank";

export const NEARBY_CATEGORIES: NearbyCategory[] = [
  "training",
  "employment",
  "government",
  "bank",
];

export interface NearbyCentre {
  latitude: number;
  longitude: number;
  /**
   * gps: the device said. place: a town we recognised. default: we do not
   * know where the person is, so this is where the openings are.
   */
  source: "gps" | "place" | "default";
  key: string | null;
  /** {"en": ..., "ta": ..., "hi": ...}. Empty for a device location. */
  names: Record<string, string>;
}

export interface NearbySchemeRef {
  id: number;
  title: string;
  organization: string;
  type: string;
}

/** Every opening in one town, pinned at the town centre. */
export interface NearbySchemePlace {
  key: string;
  names: Record<string, string>;
  latitude: number;
  longitude: number;
  distance_km: number;
  /** Always true: the record knows the town, not the street. */
  approximate: boolean;
  schemes: NearbySchemeRef[];
}

export interface NearbyResponse {
  centre: NearbyCentre;
  scheme_places: NearbySchemePlace[];
  /** Openings whose town the map does not know. Listed, never dropped. */
  unplaced_schemes: NearbySchemeRef[];
}

/** An office from OpenStreetMap. Passed through, never invented. */
export interface SupportPlace {
  id: string;
  category: NearbyCategory;
  name: string;
  names: Record<string, string>;
  latitude: number;
  longitude: number;
  distance_km: number;
  address: string | null;
  opening_hours: string | null;
  osm_url: string;
}

export interface SupportResponse {
  support_places: SupportPlace[];
  /**
   * ok: looked. unavailable: could not look just now. offline: live lookups
   * are off here and the bundled snapshot does not cover this search.
   */
  support_status: "ok" | "unavailable" | "offline";
  /** Where an ok answer came from. */
  source: "snapshot" | "live" | null;
  /** ISO date the snapshot was fetched, when it answered. */
  as_of: string | null;
  radius_km: number;
  provider: string;
  degraded: boolean;
  attribution: string;
}

export interface KnownPlace {
  key: string;
  district: string;
  names: Record<string, string>;
  latitude: number;
  longitude: number;
}
