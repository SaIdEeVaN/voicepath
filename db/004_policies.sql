-- VoicePath -- row level security
-- Apply after 003_seed.sql.
--
-- Access model for the MVP (no end-user auth, PRD section 1):
--
--   * The browser NEVER talks to Postgres. Every read and write goes through
--     the FastAPI backend, which connects with DATABASE_URL as the table owner
--     and is therefore not subject to these policies.
--   * These policies exist so that if a Supabase anon/authenticated key is ever
--     exposed -- deliberately or by accident -- the blast radius is limited to
--     the reference catalogues, and no session, transcript, profile, match or
--     question is reachable.
--   * RLS is enabled with NO permissive policy on the personal-data tables.
--     In Postgres that means: deny everything to anon and authenticated.
--
-- If end-user accounts are added later (PRD section 3, "Additional Tables"),
-- replace the deny-all blocks with owner policies keyed on auth.uid() and add
-- the matching index -- see the RLS-performance note at the bottom of this file.

-- ---------------------------------------------------------------------------
-- Reference catalogues -- world-readable, service-writable.
-- ---------------------------------------------------------------------------
alter table skill_taxonomy      enable row level security;
alter table opportunities       enable row level security;
alter table opportunity_skills  enable row level security;

drop policy if exists skill_taxonomy_public_read on skill_taxonomy;
create policy skill_taxonomy_public_read
  on skill_taxonomy for select
  to anon, authenticated
  using (true);

drop policy if exists opportunities_public_read on opportunities;
create policy opportunities_public_read
  on opportunities for select
  to anon, authenticated
  using (is_active);

drop policy if exists opportunity_skills_public_read on opportunity_skills;
create policy opportunity_skills_public_read
  on opportunity_skills for select
  to anon, authenticated
  using (true);

-- No insert/update/delete policy for anon or authenticated: catalogue writes
-- are the admin API's job, and it authenticates server-side (PRD section 6.6).

-- ---------------------------------------------------------------------------
-- Personal data -- RLS on, no policy, therefore unreachable by anon keys.
-- ---------------------------------------------------------------------------
alter table sessions           enable row level security;
alter table extracted_profiles enable row level security;
alter table extracted_skills   enable row level security;
alter table matches            enable row level security;
alter table assistant_queries  enable row level security;
alter table admin_users        enable row level security;

-- Belt and braces: even a role that somehow acquired direct grants gets nothing.
revoke all on sessions, extracted_profiles, extracted_skills,
              matches, assistant_queries, admin_users
  from anon, authenticated;

-- ---------------------------------------------------------------------------
-- Function grants
-- ---------------------------------------------------------------------------
-- Vector lookups read only the public catalogue, so they are safe to expose.
grant execute on function match_skill_taxonomy(vector, integer, double precision)
  to anon, authenticated;
grant execute on function opportunity_skill_vectors(text)
  to anon, authenticated;

-- ---------------------------------------------------------------------------
-- When user accounts arrive
-- ---------------------------------------------------------------------------
-- Add sessions.user_id uuid references auth.users(id), then:
--
--   create index sessions_user_id_idx on sessions (user_id);
--   create policy sessions_owner on sessions for all to authenticated
--     using ((select auth.uid()) = user_id);
--
-- Wrapping auth.uid() in a subselect makes Postgres evaluate it once per query
-- instead of once per row, and the index keeps the check an index scan.
