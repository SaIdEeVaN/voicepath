-- VoicePath -- scheme document store for retrieval (local only).
--
-- This is the corpus the assistant may consult when a question is about the
-- scheme itself rather than about one scheme: eligibility rules,
-- application procedure, what a component covers. Those answers live in policy
-- documents that are far too large to put in a prompt, which is the one place
-- retrieval earns its keep here.
--
-- Deliberately separate from `schemes`. Nothing in this table may
-- influence a match score: retrieval answers questions, it does not rank.
--
-- Apply after 004. Nothing deployed reads these tables yet.

create extension if not exists vector;

-- ---------------------------------------------------------------------------
-- scheme_documents -- one row per source file.
--
-- Kept apart from the chunks so a document can be re-chunked (different size,
-- better extraction) without losing its identity, and so a citation can name
-- the document a person could actually go and read.
-- ---------------------------------------------------------------------------
create table if not exists scheme_documents (
  id           bigint generated always as identity primary key,
  title        text not null,
  -- Where this came from: a filename, or better, a public URL. This is what a
  -- citation shows, so it has to mean something to a person, not just to us.
  source       text not null unique,
  -- ta | hi | en. The corpus may be mixed; retrieval is cross-lingual anyway.
  language     text not null default 'en',
  published_on date,
  created_at   timestamptz not null default now()
);

comment on table scheme_documents is
  'Source policy documents. Answers must cite one of these rows.';

-- ---------------------------------------------------------------------------
-- document_chunks -- the retrievable unit.
--
-- Chunking is where retrieval quality is won or lost. A chunk that splits an
-- eligibility clause in half is individually meaningless, and no amount of
-- prompting recovers it. `heading` and `ordinal` exist so a retrieved fragment
-- can be shown in context rather than as an orphaned paragraph.
-- ---------------------------------------------------------------------------
create table if not exists document_chunks (
  id          bigint generated always as identity primary key,
  document_id bigint not null references scheme_documents (id) on delete cascade,
  -- Position within the document, so neighbours can be fetched to widen context.
  ordinal     integer not null,
  -- The section this text sat under, when the document had structure worth
  -- keeping. Shown with the citation.
  heading     text,
  content     text not null,
  -- Same 768 dimensions as skill_taxonomy, because it is the same embedding
  -- model. Mixing models across tables would compare vectors from different
  -- spaces -- no error, just silently wrong retrieval.
  embedding   vector(768),
  -- Postgres full-text vector, maintained by the database rather than the
  -- application. Dense search misses exact strings like "NSQF Level 4";
  -- keyword search catches them. Hybrid retrieval needs both.
  tsv         tsvector generated always as (to_tsvector('simple', content)) stored,
  created_at  timestamptz not null default now(),
  constraint document_chunks_unique_ordinal unique (document_id, ordinal),
  constraint document_chunks_content_not_blank check (length(trim(content)) > 0)
);

comment on column document_chunks.embedding is
  'multilingual-e5-base, 768 dims. Written with the "passage: " prefix.';

create index if not exists document_chunks_document_idx
  on document_chunks (document_id);

create index if not exists document_chunks_tsv_idx
  on document_chunks using gin (tsv);

-- IVFFlat over cosine distance. Built after the table has rows -- an index on
-- an empty table has nothing to cluster and will be rebuilt anyway.
-- Run once the corpus is loaded:
--   create index document_chunks_embedding_idx on document_chunks
--     using ivfflat (embedding vector_cosine_ops) with (lists = 100);

-- ---------------------------------------------------------------------------
-- match_document_chunks -- nearest chunks by cosine similarity.
--
-- Mirrors match_skill_taxonomy deliberately: same operator, same shape, same
-- explicit operator qualification. `search_path = ''` hides operators, and
-- unlike tables they cannot be schema-qualified by name.
-- ---------------------------------------------------------------------------
create or replace function match_document_chunks(
  query_embedding vector(768),
  match_count     integer default 5,
  min_similarity  double precision default 0.0
)
returns table (
  chunk_id       bigint,
  document_id    bigint,
  document_title text,
  source         text,
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
    c.heading,
    c.content,
    1 - (c.embedding operator(public.<=>) query_embedding) as similarity
  from public.document_chunks c
  join public.scheme_documents d on d.id = c.document_id
  where c.embedding is not null
    and 1 - (c.embedding operator(public.<=>) query_embedding) >= min_similarity
  order by c.embedding operator(public.<=>) query_embedding
  limit greatest(match_count, 1);
$$;

comment on function match_document_chunks is
  'Dense retrieval over scheme documents. Pair with keyword search for hybrid.';

-- ---------------------------------------------------------------------------
-- RLS. Scheme documents are public policy, so they are public-read like the
-- catalogue. They carry no personal data and never should.
-- ---------------------------------------------------------------------------
alter table scheme_documents enable row level security;
alter table document_chunks enable row level security;

drop policy if exists scheme_documents_public_read on scheme_documents;
create policy scheme_documents_public_read on scheme_documents
  for select using (true);

drop policy if exists document_chunks_public_read on document_chunks;
create policy document_chunks_public_read on document_chunks
  for select using (true);
