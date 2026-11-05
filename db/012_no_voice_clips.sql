-- VoicePath -- recordings are never kept; the data should not say otherwise.
-- Apply after 011_more_skills.sql. Safe to re-run.
--
-- Decided 2026-11-05. No code path keeps a recording (backend/app/routes/
-- speech.py transcribes in memory and discards the bytes), yet the passport
-- offered "Keep my voice clips so employers can hear me say it" and stored the
-- answer in sessions.audio_retained -- a promise nothing kept. The toggle and
-- its endpoint are gone. This clears the flags it left behind on sessions that
-- hold no clip; purge_expired_audio (db/002) still runs daily from the API as
-- the safety net for clip links.

update sessions
   set audio_retained = false
 where audio_retained
   and audio_url is null;

comment on column sessions.audio_retained is
  'Always false: VoicePath never keeps recordings (2026-11-05). Kept for the '
  'check constraint that forbids an audio_url without it.';
