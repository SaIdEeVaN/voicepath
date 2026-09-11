-- VoicePath -- database functions
-- Apply after 001_schema.sql.

-- ---------------------------------------------------------------------------
-- match_skill_taxonomy
--
-- Nearest taxonomy entries for a query embedding, as cosine SIMILARITY in
-- [0, 1] rather than pgvector's distance, so callers compare against a
-- confidence threshold without re-deriving the sign convention.
--
-- Used by services/normalization.py (PRD section 4.3).
-- ---------------------------------------------------------------------------
create or replace function match_skill_taxonomy(
  query_embedding vector(768),
  match_count     integer default 5,
  min_similarity  double precision default 0.0
)
returns table (
  id            bigint,
  code          text,
  name          text,
  category      text,
  hint          text,
  display_names jsonb,
  similarity    double precision
)
language sql
stable
set search_path = ''
as $$
  select
    t.id,
    t.code,
    t.name,
    t.category,
    t.hint,
    t.display_names,
    1 - (t.embedding operator(public.<=>) query_embedding) as similarity
  from public.skill_taxonomy t
  where t.embedding is not null
    and 1 - (t.embedding operator(public.<=>) query_embedding) >= min_similarity
  order by t.embedding operator(public.<=>) query_embedding
  limit greatest(match_count, 1);
$$;

comment on function match_skill_taxonomy is
  'Nearest taxonomy entries by cosine similarity. Returns similarity in [0,1].';

-- ---------------------------------------------------------------------------
-- scheme_skill_vectors
--
-- The required-skill embedding set for every active scheme, in one round
-- trip. The matching engine needs all of them to score a profile, and pulling
-- them per-scheme would be a textbook N+1 (PRD section 4.4).
-- ---------------------------------------------------------------------------
create or replace function scheme_skill_vectors(district_filter text default null)
returns table (
  scheme_id bigint,
  skill_id       bigint,
  skill_code     text,
  skill_name     text,
  weight         numeric,
  is_essential   boolean,
  embedding      vector(768)
)
language sql
stable
set search_path = ''
as $$
  select
    os.scheme_id,
    os.skill_id,
    t.code,
    t.name,
    os.weight,
    os.is_essential,
    t.embedding
  from public.scheme_skills os
  join public.skill_taxonomy t on t.id = os.skill_id
  join public.schemes o on o.id = os.scheme_id
  where o.is_active
    and (district_filter is null or o.district = district_filter);
$$;

-- ---------------------------------------------------------------------------
-- purge_expired_audio
--
-- Safety net for PRD section 7. Any session that did not opt in must not hold
-- an audio_url; any opted-in clip older than the retention window is dropped.
-- Schedule with pg_cron:
--   select cron.schedule('purge-audio', '0 3 * * *', $$select purge_expired_audio(90)$$);
--
-- Deleting the row's URL does not delete the Storage object -- the backend
-- job in services/retention.py does that, then calls this to clear the rows.
-- ---------------------------------------------------------------------------
create or replace function purge_expired_audio(retain_days integer default 90)
returns integer
language plpgsql
security definer
set search_path = ''
as $$
declare
  cleared integer;
begin
  update public.sessions
     set audio_url = null,
         audio_retained = false
   where audio_url is not null
     and (not audio_retained
          or created_at < now() - make_interval(days => retain_days));
  get diagnostics cleared = row_count;
  return cleared;
end;
$$;

revoke execute on function purge_expired_audio(integer) from public, anon, authenticated;
