-- VoicePath -- record which language a stored explanation was written in.
-- Apply after 006_schemes_rename.sql.
--
-- Why this column has to exist.
--
-- `matches.explanation_text` and `explanation_bullets` hold prose the server
-- wrote, in one language, at the moment the match was computed. The row said
-- nothing about which language that was -- so a reader who switched to Tamil
-- on the detail screen kept seeing the English sentences, and nothing in the
-- system could tell they were stale. There was no way to ask the question.
--
-- With the language recorded, `GET /api/schemes/{id}/match/{session}?language=`
-- can answer it cheaply: return the stored text when it already matches, and
-- rewrite the sentences from the stored scores when it does not.
--
-- Deliberately nullable. Rows written before this migration have prose in an
-- unknown language, and claiming otherwise would be a lie the code would then
-- trust. A null reads as "unknown", which correctly forces a rewrite on the
-- first request that names a language.

alter table matches
  add column if not exists explanation_language text;

comment on column matches.explanation_language is
  'BCP-47 primary subtag the explanation prose was generated in. Null means '
  'unknown -- written before this column existed -- which forces a rewrite '
  'rather than serving text in a language the reader may not read.';

-- Only ever compared against a two-letter primary subtag, and only for the
-- three languages the product speaks. A wider value would mean the writer and
-- the reader disagree about what to compare.
alter table matches
  drop constraint if exists matches_explanation_language_known;

alter table matches
  add constraint matches_explanation_language_known check (
    explanation_language is null
    or explanation_language in ('ta', 'hi', 'en')
  );
