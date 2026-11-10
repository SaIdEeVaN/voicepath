-- VoicePath -- 015: vectors from multilingual-e5-small (384 numbers, not 768)
--
-- Decided 2026-11-10 with the owner. The Hugging Face Inference API, which ran
-- multilingual-e5-base for us, has answered 402 Payment Required since
-- 2026-11-04. The API now runs multilingual-e5-small itself, which needs no
-- key and cannot run out of credits, but whose vectors have 384 numbers and
-- mean nothing next to e5-base's. So:
--
--   * both vector columns become vector(384), and every stored vector is
--     cleared -- a vector from the other model is not a smaller-but-valid
--     one, it is a wrong one;
--   * the three vector functions are recreated with `vector` of no fixed
--     size, so the next model change touches only the columns;
--   * the API refills the vectors itself: on its next start (and every
--     minute while this migration is missing) it embeds the 71 skills, then
--     every passage of every document not rejected, a round of 16 at a time.
--     About 25-50 minutes on the free container. Meanwhile skills are still
--     recognised by name and alias, and documents are searched by keyword.
--
-- Safe before or after the code that needs it: until this is applied the API
-- sees the 768-number columns, stops embedding rather than fail, and /health
-- names this file (services/db.py, VECTOR_COLUMNS).
--
-- Re-running is harmless: the columns are already the size, and the vectors
-- the API has written since are cleared and written again.

begin;

-- The HNSW index is rebuilt for the new size.
drop index if exists skill_taxonomy_embedding_idx;

alter table skill_taxonomy
  alter column embedding type vector(384) using null;

alter table document_chunks
  alter column embedding type vector(384) using null;

create index skill_taxonomy_embedding_idx
  on skill_taxonomy using hnsw (embedding vector_cosine_ops);

comment on column document_chunks.embedding is
  'multilingual-e5-small (int8 ONNX), 384 dims, since 2026-11-10. Embedded from '
  'title | heading | content with the "passage: " prefix.';
comment on column skill_taxonomy.embedding is
  'multilingual-e5-small (int8 ONNX), 384 dims, since 2026-11-10. Embedded from '
  'catalogue.embedding_text with the "passage: " prefix.';

-- ---------------------------------------------------------------------------
-- The vector functions, no longer tied to one size
-- ---------------------------------------------------------------------------

create or replace function match_skill_taxonomy(
  query_embedding vector,
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

-- Its result columns change (vector(768) to vector), which create-or-replace
-- may refuse, so it is dropped and made again, with the grant it had.
drop function if exists scheme_skill_vectors(text);

create function scheme_skill_vectors(district_filter text default null)
returns table (
  scheme_id    bigint,
  skill_id     bigint,
  skill_code   text,
  skill_name   text,
  weight       numeric,
  is_essential boolean,
  embedding    vector
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

grant execute on function scheme_skill_vectors(text) to anon, authenticated;

create or replace function match_document_chunks(
  query_embedding vector,
  match_count     integer default 5,
  min_similarity  double precision default 0.0
)
returns table (
  chunk_id       bigint,
  document_id    bigint,
  document_title text,
  source         text,
  source_url     text,
  heading        text,
  content        text,
  similarity     double precision
)
language sql
stable
set search_path = ''
as $$
  select
    c.id,
    d.id,
    d.title,
    d.source,
    d.source_url,
    c.heading,
    c.content,
    1 - (c.embedding operator(public.<=>) query_embedding) as similarity
  from public.document_chunks c
  join public.scheme_documents d on d.id = c.document_id
  where d.status = 'active'
    and c.embedding is not null
    and 1 - (c.embedding operator(public.<=>) query_embedding) >= min_similarity
  order by c.embedding operator(public.<=>) query_embedding
  limit greatest(match_count, 1);
$$;

commit;

-- Check (expect vector(384) twice, and 0 vectors until the API refills them):
--   select c.relname, format_type(a.atttypid, a.atttypmod)
--   from pg_attribute a join pg_class c on c.oid = a.attrelid
--   where a.attname = 'embedding' and c.relname in ('skill_taxonomy', 'document_chunks');
--   select count(embedding) from skill_taxonomy;
--   select count(embedding) from document_chunks;
