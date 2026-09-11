-- VoicePath -- rename opportunities to schemes, and add official_url.
--
-- 001-004 already describe the renamed world, so a database created from
-- scratch never needs this file. It exists for a database that was built
-- before the rename: it moves the existing tables rather than rebuilding them,
-- so no row is lost and no id changes.
--
-- Apply after 004 (and after 005 if the retrieval branch is in use).
--
-- TIMING. A deployment still running the pre-rename code reads `opportunities`
-- and will break the moment these tables move. The compatibility views at the
-- bottom cover that window for reads, which is what the matching path needs;
-- writes through the admin API will fail until the new code is live. Apply
-- this, deploy, then drop the views.

-- ---------------------------------------------------------------------------
-- Tables and columns.
--
-- `alter table ... rename` keeps the data, the primary keys and the foreign
-- keys pointing at it. Indexes and constraints keep their old names, which is
-- untidy but harmless; renaming those is done below only where the name is
-- visible in application code.
-- ---------------------------------------------------------------------------
alter table if exists opportunities rename to schemes;
alter table if exists opportunity_skills rename to scheme_skills;

alter table if exists scheme_skills rename column opportunity_id to scheme_id;
alter table if exists matches rename column opportunity_id to scheme_id;
alter table if exists assistant_queries rename column opportunity_id to scheme_id;

-- ---------------------------------------------------------------------------
-- official_url -- where this scheme is described by the government itself.
--
-- Distinct from source_reference, which is a scheme code to quote at an office
-- ("OGD/TN/SLM/AUTO/2024/0117"). This is a page a person can open and read, and
-- it is what the assistant cites when someone asks where a scheme is published.
-- Nullable: a district opening sourced from a spreadsheet has no such page, and
-- inventing one would be worse than leaving it empty.
-- ---------------------------------------------------------------------------
alter table if exists schemes add column if not exists official_url text;

comment on column schemes.official_url is
  'Official government page for this scheme. Cited verbatim; never guessed.';

-- Only an absolute http(s) URL. A half-remembered path would be shown to a
-- person as though the government published it.
alter table schemes drop constraint if exists schemes_official_url_absolute;
alter table schemes add constraint schemes_official_url_absolute check (
  official_url is null or official_url ~ '^https?://[^[:space:]]+$'
);

-- ---------------------------------------------------------------------------
-- The vector function, renamed to match its table.
-- ---------------------------------------------------------------------------
drop function if exists opportunity_skill_vectors(text);

create or replace function scheme_skill_vectors(district_filter text default null)
returns table (
  scheme_id    bigint,
  skill_id     bigint,
  skill_code   text,
  skill_name   text,
  weight       numeric,
  is_essential boolean,
  embedding    vector(768)
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
-- RLS follows the table, but the policies were named for the old one.
-- ---------------------------------------------------------------------------
alter table schemes enable row level security;
alter table scheme_skills enable row level security;

drop policy if exists opportunities_public_read on schemes;
drop policy if exists schemes_public_read on schemes;
create policy schemes_public_read on schemes for select using (true);

drop policy if exists opportunity_skills_public_read on scheme_skills;
drop policy if exists scheme_skills_public_read on scheme_skills;
create policy scheme_skills_public_read on scheme_skills for select using (true);

-- ---------------------------------------------------------------------------
-- Temporary compatibility views.
--
-- Read-only, and only so a deployment still running the old code keeps
-- answering while the new code ships. Drop them once it has:
--
--   drop function if exists opportunity_skill_vectors(text);
--   drop view if exists opportunity_skills;
--   drop view if exists opportunities;
--
-- They are views, not tables: an insert through them fails loudly rather than
-- writing to a shape nothing else reads.
-- ---------------------------------------------------------------------------
-- The pre-rename code also calls this function by name. Dropping it without
-- this shim takes the deployment's matching path down while the views make
-- everything else look healthy -- which is exactly how it was found.
create or replace function opportunity_skill_vectors(district_filter text default null)
returns table (
  opportunity_id bigint,
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
  select os.scheme_id, os.skill_id, t.code, t.name, os.weight,
         os.is_essential, t.embedding
  from public.scheme_skills os
  join public.skill_taxonomy t on t.id = os.skill_id
  join public.schemes o on o.id = os.scheme_id
  where o.is_active
    and (district_filter is null or o.district = district_filter);
$$;

create or replace view opportunities as select * from schemes;
create or replace view opportunity_skills as
  select scheme_id as opportunity_id, skill_id, weight, is_essential
  from scheme_skills;
