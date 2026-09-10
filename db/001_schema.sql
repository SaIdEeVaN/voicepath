-- VoicePath -- schema (PRD section 3)
-- Target: Supabase Postgres. Apply with: psql "$DATABASE_URL" -f db/001_schema.sql
--
-- Conventions applied throughout:
--   * lowercase, snake_case identifiers (no quoting needed anywhere)
--   * every foreign-key column carries its own index
--   * RLS enabled on every public table; see 004_policies.sql
--   * embeddings are 768-dim (multilingual-e5-base). If you swap EMBEDDING_MODEL
--     for a different dimensionality, change vector(768) here and re-embed.

create extension if not exists vector;
create extension if not exists pgcrypto;   -- gen_random_uuid()

-- ---------------------------------------------------------------------------
-- skill_taxonomy -- the standard skill vocabulary. Language-independent.
-- Source of truth for skills; never hardcode skill lists in the frontend.
-- ---------------------------------------------------------------------------
create table if not exists skill_taxonomy (
  id          bigint generated always as identity primary key,
  code        text not null unique,
  name        text not null,
  category    text not null,
  -- Aliases across languages/registers. Used to build a richer embedding text
  -- and to give the LLM disambiguation step something concrete to reason over.
  aliases     jsonb not null default '[]'::jsonb,
  -- Short plain-language hint shown on the disambiguation screen.
  hint        text,
  -- What the skill is called in each language, e.g. {"ta": "...", "hi": "..."}.
  -- The code stays language-independent; only the label a person reads is
  -- translated. English lives in `name` and is the fallback.
  display_names jsonb not null default '{}'::jsonb,
  embedding   vector(768),
  created_at  timestamptz not null default now(),
  constraint skill_taxonomy_code_format check (code ~ '^SK[0-9]{3,}$'),
  constraint skill_taxonomy_aliases_is_array check (jsonb_typeof(aliases) = 'array'),
  constraint skill_taxonomy_display_names_is_object check (
    jsonb_typeof(display_names) = 'object'
  )
);

comment on table skill_taxonomy is
  'Standard skill vocabulary. embedding is a multilingual embedding of name + aliases.';

-- HNSW over cosine distance: normalization looks up nearest taxonomy entries
-- for a raw spoken phrase. Populated by scripts/embed_taxonomy.py after seeding.
create index if not exists skill_taxonomy_embedding_idx
  on skill_taxonomy using hnsw (embedding vector_cosine_ops);

create index if not exists skill_taxonomy_category_idx
  on skill_taxonomy (category);

-- ---------------------------------------------------------------------------
-- opportunities -- district-level skilling / livelihood opportunities.
-- ---------------------------------------------------------------------------
create table if not exists opportunities (
  id                      bigint generated always as identity primary key,
  title                   text not null,
  organization            text not null,
  location                text not null,
  district                text,
  type                    text not null,
  minimum_experience      numeric(4,1) not null default 0,
  certifications_required jsonb not null default '[]'::jsonb,
  salary_min              integer,
  salary_max              integer,
  nsqf_level              text,
  source_reference        text,
  -- Verbatim source text. The explanation layer is only ever allowed to ground
  -- itself in this row; nothing outside it may be asserted to a user.
  description             text,
  is_active               boolean not null default true,
  created_at              timestamptz not null default now(),
  updated_at              timestamptz not null default now(),
  constraint opportunities_type_allowed check (
    type in ('Full-time', 'Part-time', 'Training', 'Apprenticeship', 'Self-employment support')
  ),
  constraint opportunities_min_exp_nonneg check (minimum_experience >= 0),
  constraint opportunities_salary_order check (
    salary_min is null or salary_max is null or salary_min <= salary_max
  ),
  constraint opportunities_salary_nonneg check (
    (salary_min is null or salary_min >= 0) and (salary_max is null or salary_max >= 0)
  ),
  constraint opportunities_certs_is_array check (
    jsonb_typeof(certifications_required) = 'array'
  )
);

comment on column opportunities.description is
  'Verbatim source text. The explanation layer may ground itself only in this row.';

-- Matching scans the active set and filters by district; this covers both.
create index if not exists opportunities_active_district_idx
  on opportunities (district)
  where is_active;

-- ---------------------------------------------------------------------------
-- opportunity_skills -- join table: opportunity -> required taxonomy skills.
-- ---------------------------------------------------------------------------
create table if not exists opportunity_skills (
  opportunity_id bigint not null references opportunities (id) on delete cascade,
  skill_id       bigint not null references skill_taxonomy (id) on delete restrict,
  -- Weight lets one opportunity treat a skill as core vs. nice-to-have.
  weight         numeric(3,2) not null default 1.0,
  is_essential   boolean not null default true,
  primary key (opportunity_id, skill_id),
  constraint opportunity_skills_weight_range check (weight > 0 and weight <= 1)
);

-- The PK already indexes (opportunity_id, ...). The reverse direction does not.
create index if not exists opportunity_skills_skill_id_idx
  on opportunity_skills (skill_id);

-- ---------------------------------------------------------------------------
-- sessions -- one row per voice interaction.
-- Raw audio is NOT retained by default (PRD section 7, data-minimization).
-- ---------------------------------------------------------------------------
create table if not exists sessions (
  id                 uuid primary key default gen_random_uuid(),
  created_at         timestamptz not null default now(),
  language_detected  text,
  transcript         text,
  audio_retained     boolean not null default false,
  audio_url          text,
  -- Which STT provider produced the transcript, for auditability.
  stt_provider       text,
  -- Invariant, not a convention: a URL may only exist when the user opted in.
  constraint sessions_audio_url_requires_optin check (
    audio_retained or audio_url is null
  )
);

comment on constraint sessions_audio_url_requires_optin on sessions is
  'PRD section 7: raw audio is deleted post-transcription unless the user opted in.';

create index if not exists sessions_created_at_idx on sessions (created_at desc);

-- ---------------------------------------------------------------------------
-- extracted_profiles -- structured output of the LLM extraction layer.
-- ---------------------------------------------------------------------------
create table if not exists extracted_profiles (
  id                  uuid primary key default gen_random_uuid(),
  session_id          uuid not null references sessions (id) on delete cascade,
  experience_years    numeric(4,1),
  experience_context  text,
  education           jsonb not null default '[]'::jsonb,
  certifications      jsonb not null default '[]'::jsonb,
  location            text,
  work_preferences    jsonb not null default '[]'::jsonb,
  uncertainty_flags   jsonb not null default '[]'::jsonb,
  created_at          timestamptz not null default now(),
  constraint extracted_profiles_exp_nonneg check (
    experience_years is null or experience_years >= 0
  ),
  constraint extracted_profiles_jsonb_arrays check (
    jsonb_typeof(education) = 'array'
    and jsonb_typeof(certifications) = 'array'
    and jsonb_typeof(work_preferences) = 'array'
    and jsonb_typeof(uncertainty_flags) = 'array'
  )
);

-- One profile per session keeps the pipeline idempotent: re-running extract
-- replaces rather than accumulates.
create unique index if not exists extracted_profiles_session_id_key
  on extracted_profiles (session_id);

-- ---------------------------------------------------------------------------
-- extracted_skills -- raw skill mentions, pre-normalization.
-- evidence_phrase is NOT NULL by design: PRD section 7 requires every
-- normalized skill to stay traceable to the words the user actually said.
-- ---------------------------------------------------------------------------
create table if not exists extracted_skills (
  id                   uuid primary key default gen_random_uuid(),
  profile_id           uuid not null references extracted_profiles (id) on delete cascade,
  raw_name             text not null,
  evidence_phrase      text not null,
  normalized_skill_id  bigint references skill_taxonomy (id) on delete set null,
  -- Similarity that produced normalized_skill_id, kept for auditability and
  -- for deciding whether to surface the skill for user disambiguation.
  match_confidence     numeric(4,3),
  needs_disambiguation boolean not null default false,
  -- Candidate taxonomy entries offered to the user when confidence is low.
  candidates           jsonb not null default '[]'::jsonb,
  user_confirmed       boolean not null default false,
  created_at           timestamptz not null default now(),
  constraint extracted_skills_evidence_not_blank check (length(btrim(evidence_phrase)) > 0),
  constraint extracted_skills_confidence_range check (
    match_confidence is null or (match_confidence >= 0 and match_confidence <= 1)
  ),
  constraint extracted_skills_candidates_is_array check (jsonb_typeof(candidates) = 'array')
);

comment on column extracted_skills.evidence_phrase is
  'The exact spoken phrase that produced this extraction. Never synthesised.';

create index if not exists extracted_skills_profile_id_idx
  on extracted_skills (profile_id);

create index if not exists extracted_skills_normalized_skill_id_idx
  on extracted_skills (normalized_skill_id)
  where normalized_skill_id is not null;

-- ---------------------------------------------------------------------------
-- matches -- computed, explainable match results.
-- Scores come from the deterministic engine (PRD sections 4.4 / 8); the LLM
-- only fills explanation_text and may never change a score or a rank.
-- ---------------------------------------------------------------------------
create table if not exists matches (
  id                     uuid primary key default gen_random_uuid(),
  session_id             uuid not null references sessions (id) on delete cascade,
  opportunity_id         bigint not null references opportunities (id) on delete cascade,
  skill_similarity_score numeric(5,4) not null,
  experience_score       numeric(5,4) not null,
  eligibility_score      numeric(5,4) not null,
  location_score         numeric(5,4) not null,
  overall_score          numeric(5,4) not null,
  rank                   integer not null,
  explanation_text       text,
  -- The bullet list rendered in the UI, each grounded in a stored fact.
  explanation_bullets    jsonb not null default '[]'::jsonb,
  created_at             timestamptz not null default now(),
  unique (session_id, opportunity_id),
  constraint matches_scores_are_fractions check (
    skill_similarity_score between 0 and 1
    and experience_score between 0 and 1
    and eligibility_score between 0 and 1
    and location_score between 0 and 1
    and overall_score between 0 and 1
  ),
  constraint matches_rank_positive check (rank > 0),
  constraint matches_bullets_is_array check (jsonb_typeof(explanation_bullets) = 'array')
);

-- The feed reads "top N for this session, best first".
create index if not exists matches_session_rank_idx
  on matches (session_id, rank);

create index if not exists matches_opportunity_id_idx
  on matches (opportunity_id);

-- ---------------------------------------------------------------------------
-- assistant_queries -- follow-up spoken Q&A log.
-- ---------------------------------------------------------------------------
create table if not exists assistant_queries (
  id             uuid primary key default gen_random_uuid(),
  session_id     uuid not null references sessions (id) on delete cascade,
  opportunity_id bigint references opportunities (id) on delete set null,
  question_text  text not null,
  answer_text    text not null,
  -- Where the answer came from, e.g. 'from the job listing'. Shown to the user.
  source_note    text,
  created_at     timestamptz not null default now()
);

create index if not exists assistant_queries_session_id_idx
  on assistant_queries (session_id, created_at desc);

create index if not exists assistant_queries_opportunity_id_idx
  on assistant_queries (opportunity_id)
  where opportunity_id is not null;

-- ---------------------------------------------------------------------------
-- admin_users -- Phase 2. Role gate for /api/admin/*.
-- The API verifies the role server-side (PRD section 6.6); this is the source.
-- ---------------------------------------------------------------------------
create table if not exists admin_users (
  id          uuid primary key default gen_random_uuid(),
  email       text not null unique,
  role        text not null default 'editor',
  -- sha256 of the API token. The plaintext token is never stored.
  token_hash  text not null unique,
  is_active   boolean not null default true,
  created_at  timestamptz not null default now(),
  constraint admin_users_role_allowed check (role in ('viewer', 'editor', 'owner'))
);

create index if not exists admin_users_token_hash_idx
  on admin_users (token_hash)
  where is_active;

-- ---------------------------------------------------------------------------
-- updated_at maintenance
-- ---------------------------------------------------------------------------
create or replace function set_updated_at()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists opportunities_set_updated_at on opportunities;
create trigger opportunities_set_updated_at
  before update on opportunities
  for each row execute function set_updated_at();
