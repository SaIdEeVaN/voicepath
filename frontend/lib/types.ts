/**
 * Wire types. These mirror `backend/app/models/schemas.py` exactly -- if you
 * change one, change the other.
 */

export type Language = "ta" | "hi" | "en";
export type LanguageOrAuto = Language | "auto";

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
}

export interface Citation {
  source: string;
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
}

/** What typed text on the understanding screen turned out to be. */
export interface AddSkillResponse {
  accepted: boolean;
  kind: "work" | "question" | "neither";
  skills: ExtractedSkill[];
  question: string | null;
  provider: string;
}
