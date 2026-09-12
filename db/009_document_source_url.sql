-- VoicePath -- carry a document's URL through retrieval.
-- Apply after 008_drop_compatibility_views.sql.
--
-- `scheme_documents.source_url` has existed since 005, but only pages fetched
-- by web search ever had one: the ingest script never passed a URL for a local
-- PDF, and `match_document_chunks` did not return the column, so nothing
-- downstream could have used it anyway.
--
-- The effect was that an answer drawn from a guideline cited
-- "NLMGuidelinesJan2025.pdf" -- a filename, which is not something a person can
-- follow. The point of a citation here is that someone can go and read the rule
-- themselves, or take it to an office. A name they cannot look up does not do
-- that.
--
-- `create or replace function` cannot change a function's return type, so this
-- drops and recreates it. The signature is otherwise identical.
--
-- The URLs themselves are filled in by hand, in
-- `backend/data/scheme_docs/sources.json`. Nothing in this codebase constructs
-- a URL -- `services/websearch.py` consults no model precisely so that it
-- cannot invent one -- and a document with no recorded URL still cites its
-- name, exactly as before.
--
-- ---------------------------------------------------------------------------
-- A SECOND, UNRELATED FIX, here because it lives in this same function.
-- ---------------------------------------------------------------------------
--
-- `scheme_documents.status` was written and never read. A page fetched from a
-- domain outside the .gov.in family is stored `pending_verification` so that
-- an admin must approve it before the system will assert anything from it --
-- that is the whole point of the tiering in `services/websearch.py`, and
-- `/api/admin/sources` exists to action it.
--
-- But neither this function nor the keyword query filtered on it. A pending
-- page was retrievable and citable the moment it was stored, and rejecting one
-- did not withdraw it either. The gate was recorded and never enforced.
--
-- Both paths filter on `status = 'active'` now.

drop function if exists match_document_chunks(vector(768), integer, double precision);

create function match_document_chunks(
  query_embedding vector(768),
  match_count     integer default 5,
  min_similarity  double precision default 0.0
)
returns table (
  chunk_id       bigint,
  document_id    bigint,
  document_title text,
  source         text,
  -- The government's own page for this document. Null where nobody has
  -- recorded one, which is the honest state rather than a gap to be filled
  -- with a guess.
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

comment on function match_document_chunks is
  'Dense retrieval over active scheme documents. Pair with keyword search for '
  'hybrid. Pending and rejected sources are excluded here, which is where the '
  'admin verification gate is actually enforced.';
