-- VoicePath -- a secret key for every session.
-- Apply BEFORE deploying the code that writes it. Safe to re-run.
--
-- Until 2026-11-05 a session's id was all it took to read or change it, and
-- the id travels in request paths (/api/sessions/{id}), so in access logs.
-- Each session now also has a 256-bit key, handed to the person once and sent
-- back only in a header; this column holds its SHA-256, never the key.
-- Sessions created before this have no hash and are refused with "please
-- start again" (decided 2026-11-05) -- see repository._require_key.

alter table sessions add column if not exists key_hash text;

comment on column sessions.key_hash is
  'SHA-256 of the session''s secret key (hex). Null only for sessions from '
  'before 2026-11-05, which can no longer be opened.';
