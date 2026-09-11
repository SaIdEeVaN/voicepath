-- VoicePath -- retire the opportunities compatibility shims.
-- Apply after 007_match_language.sql.
--
-- 006 renamed `opportunities` to `schemes` and left three read-only shims
-- behind -- two views and a function -- so that a deployment still running the
-- pre-rename code kept answering while the new code shipped. 006 says in as
-- many words to drop them once it had. It had; nobody did.
--
-- Supabase's database linter then flagged both views as ERROR-level
-- `security_definer_view`. That is not a quirk of the linter. A Postgres view
-- runs as its owner unless it is created `with (security_invoker = on)`, these
-- were not, and their owner is `postgres`. So every read through
-- `public.opportunities` was evaluated with the owner's privileges and
-- **bypassed row level security on `schemes` entirely**.
--
-- Nothing was exposed by it in practice: `schemes` and `scheme_skills` both
-- carry a public-read policy, so the rows reachable through the view are the
-- rows anyone could already select. The danger was latent rather than actual --
-- the day someone narrows either policy, the view would have gone on serving
-- what the policy had just withdrawn, silently and from a name no code
-- references any more.
--
-- Dropping is the right fix rather than recreating them with
-- `security_invoker = on`: these exist only to serve code that no longer runs.
-- Verified before writing this file -- no reference to `opportunit%` survives
-- anywhere in backend/, frontend/, or db/ outside 006 itself.
--
-- A database built from 001 onward never had these, so this file is a no-op
-- there. It is written to be safe either way.

-- The function first: it is the one the pre-rename matching path called, and
-- dropping it while the views remained is what would leave a deployment
-- looking healthy while matching was down. Nothing calls it now.
drop function if exists opportunity_skill_vectors(text);

drop view if exists opportunity_skills;
drop view if exists opportunities;

-- ---------------------------------------------------------------------------
-- If a compatibility view is ever needed again
-- ---------------------------------------------------------------------------
--
-- Create it `with (security_invoker = on)` so it is evaluated as the querying
-- user and the underlying table's RLS still applies:
--
--   create view opportunities with (security_invoker = on) as
--     select * from schemes;
--
-- Postgres 15 and later only, which this database is (17.6). Without that
-- option the view silently becomes an RLS bypass, which is the whole reason
-- this file exists.
