# VoicePath — Build Status

> **This file is the live todo list.** It is updated every time a task is completed.
> Last updated: 2026-09-10 (open-source stack migration)

**Project root:** `C:\Users\Sai Dixit\voicepath`
**Sources:** `PRD_File_For_Project.md` (spec) · `VoicePath Mockups.html` (design canvas, unpacked)

---

## Progress

| Phase | Status |
|---|---|
| 0. Scaffold & docs | ✅ Done |
| 1. Database (schema + seed) | ✅ Done |
| 2. Backend core (config, db, providers) | ✅ Done |
| 3. Backend pipeline (extract → normalize → match → explain) | ✅ Done |
| 4. Backend routes + rate limiting | ✅ Done |
| 5. Backend tests | ✅ Done — **178 passing** |
| 6. Frontend scaffold + design tokens | ✅ Done |
| 7. Frontend screens | ✅ Done — all 8 |
| 8. Admin (Phase 2) | ✅ Done |
| 9. Verification | ✅ Done — tests, typecheck, build, live end-to-end |

**The project is complete and running.** Everything below is detail.

---

## How to run it

```bash
# Backend  (http://localhost:8000)
cd backend
pip install -r requirements-ml.txt   # Whisper, Piper, embeddings (~3GB)
python -m app.scripts.fetch_voices   # Piper voices for ta/hi/en (~190MB)
uvicorn app.main:app --reload --port 8000

# Frontend (http://localhost:3000)
cd frontend && npm install && npm run dev
```

One key only: `LLM_API_KEY` (Groq, free). Everything else runs locally.

`README.md` has the full setup, including Supabase and the offline mode.

---

## Task checklist

### Phase 0 — Scaffold & docs ✅
- [x] Directory tree
- [x] `STATUS.md` (this file)
- [x] `README.md` — setup, the pipeline, the three enforced rules
- [x] `.gitignore` — `.env` protected before any key was written

### Phase 1 — Database ✅
- [x] `db/001_schema.sql` — 9 tables, pgvector, constraints, FK indexes
- [x] `db/002_functions.sql` — `match_skill_taxonomy`, `opportunity_skill_vectors`, `purge_expired_audio`
- [x] `db/003_seed.sql` — 44 skills + 16 Salem/Erode opportunities + localized labels
- [x] `db/004_policies.sql` — RLS: catalogues public-read, personal data unreachable by anon keys
- [x] `db/README.md`

### Phase 2 — Backend core ✅
- [x] `config.py` — provider auto-downgrade, weight-sum validation, reasoning headroom
- [x] `services/db.py` — asyncpg pool, pgvector literals, healthcheck
- [x] `services/llm.py` — Groq / Gemini / offline, reasoning-model handling
- [x] `services/embeddings.py` — multilingual-e5 + deterministic hashing fallback
- [x] `services/stt.py` (faster-whisper), `services/tts.py` (Piper), browser handoff
- [x] `services/ner.py` — IndicNER entity spans; built, not yet consumed
- [x] `services/taxonomy.py` — vector search, exact alias index, localized labels
- [x] `services/opportunities.py`, `services/repository.py`, `models/schemas.py`

### Phase 3 — Backend pipeline ✅
- [x] `extraction.py` — **evidence verified against the transcript; ungrounded skills dropped**
- [x] `normalization.py` — exact alias → embedding → LLM assist → user disambiguation
- [x] `matching.py` — deterministic 50/25/15/10, stable ties, cross-script place resolution
- [x] `explanation.py` — grounded bullets in ta/hi/en, cannot re-rank
- [x] `assistant.py` — Q&A over stored fields only
- [x] `prompts/text.py` — all four prompts, reviewable on their own

### Phase 4 — Backend routes ✅
- [x] All 7 PRD routes, plus `/client-transcript`, `/taxonomy`, passport, retention
- [x] `/api/admin/*` — server-side role check, sha256 tokens, bootstrap that self-disables
- [x] Rate limiting on public routes · `GET /health` reporting every provider honestly

### Phase 5 — Backend tests ✅ (178 passing)
- [x] `test_matching.py` — weights, determinism, each component, grounding
- [x] `test_extraction.py` — evidence grounding in ta/hi/en, invention rejected
- [x] `test_normalization.py` — alias matching across scripts, no silent upgrades
- [x] `test_explanation.py` — cannot re-rank, no eligibility promises, no jargon
- [x] `test_places.py` — Tamil/Hindi/English place names and case endings
- [x] `test_localization.py` — every skill has ta/hi labels; sentences stay in one language
- [x] `test_catalogue_sync.py` — SQL and Python catalogues cannot drift
- [x] `test_api.py` — full pipeline, privacy invariants, admin gate

### Phase 6 — Frontend scaffold ✅
- [x] Next 16.3.4, React 19, TS strict, Tailwind v4
- [x] `globals.css` token layer — every colour named; no hardcoded colours in pages
- [x] Bricolage Grotesque + Instrument Sans + Anek Tamil + Anek Devanagari
- [x] `lib/i18n.ts` — ta/hi/en copy written in each language, not translated
- [x] `lib/api.ts`, `lib/session.tsx`, `lib/browser-speech.ts`, `lib/recorder.ts`

### Phase 7 — Frontend screens ✅
- [x] `/` Landing — statement, mic, other languages as their own sentences
- [x] `/speak` — **waveform driven by live mic analyser data**, not a timer
- [x] `/understanding` — editable cards, each showing the words that produced it
- [x] `/understanding/disambiguate` — low-confidence screen, "leave it out" is a real answer
- [x] `/passport` — Skill Passport + audio-retention toggle
- [x] `/opportunities` — ranked feed, reasons weighted equal to titles
- [x] `/opportunities/[id]` — RSC detail + score bars + Ask VoicePath

### Phase 8 — Admin ✅
- [x] `/admin/opportunities`, `/admin/taxonomy`, `/admin/sessions` (read-only, no transcripts)

### Phase 9 — Verification ✅
- [x] `pytest` — 178 passed
- [x] `npx tsc --noEmit` — clean
- [x] `next build` — 12 routes
- [x] Both servers running; RSC detail page pulling live backend data
- [x] Live end-to-end in Tamil through the real LLM

---

## Live verification (Tamil, real LLM)

Input: *"எனக்கு ஆறு வருஷமா பைக் ரிப்பேர் தெரியும். சேலத்துல ஒரு கடையில வேலை பாத்தேன்…"*

- Extracted 6 years, location Salem, 4 skills with **verbatim Tamil evidence**
- Flagged welding as uncertain because they said "கொஞ்சம்" (a little)
- Ranked 16 opportunities; top match 100%, location scored 1.00
- Explained in Tamil: *"நீங்கள் வெல்டிங் செய்கிறீர்கள் — இந்த வேலை அதுவே."*
- Answered *"எனக்கு சான்றிதழ் இல்லை. பிரச்சனையா?"* from the listing, in Tamil

---

## Decisions & assumptions

1. **Runs with zero API keys.** Every provider has an offline implementation and the app
   downgrades automatically. Offline mode is never disguised — `/health`, response bodies
   and a UI banner all say so.
2. **Offline speech uses the browser, not fakes.** Web Speech API — real on-device
   recognition and synthesis. No canned transcript is ever passed off as real.
3. **Evidence is verified, not trusted.** `extraction._validate` checks every quote
   against the transcript and drops what it cannot find.
4. **The explanation layer has no return path to a score.** "Must not re-rank" is
   structural, not a rule the model is asked to follow.
5. **Exact alias matches beat embeddings.** A node's embedding blends ~12 aliases, so an
   exact hit scores below what its exactness deserves. Exact, not substring — so "welding
   certificate" cannot be upgraded to "welding".
6. **Framer Motion is used once**, for results arriving in rank order. All other motion is
   CSS: the waveform runs off `requestAnimationFrame` and must not re-render React 60×/s.
7. **No end-user auth** (PRD defers it). RLS contains leaked anon keys; the API is the real
   access control. The browser never touches Postgres.
8. **Embedding dimension 768.** Changing the model means changing `vector(768)` and
   re-running `embed_taxonomy`.

---

## Bugs found and fixed during the build

Each was caught by a test or by a live run, not by inspection.

- `extraction._validate` assigned `uncertainty_flags` *after* appending to it, discarding
  the "years not clear" flag.
- `explain_offline` appended the missing-certificate bullet last, where the 4-bullet cap
  cut it — the most consequential sentence was the one being dropped.
- Nothing normalized at all in offline mode (see decision 5).
- Location had no town→district knowledge: a person in Attur scored as far from Salem as
  someone in Kolkata.
- **Place names never matched across scripts.** A Tamil speaker saying "சேலத்துல" (*in
  Salem*) scored 0.20 against a Salem job and was told it was "far from your town".
- **English skill names inside Tamil sentences** — the taxonomy had no localized labels.
  All 44 skills now carry Tamil and Hindi names.
- `explanation_provider` reported the *configured* LLM even when templates produced the
  text. It now reports what actually ran (`offline`, `sarvam`, or `offline+sarvam`).
- `LLM_MODEL` defaulted to `sarvam-m`, which the API has deprecated — the PRD said
  Sarvam-105B all along.
- Sarvam-105B is a **reasoning model**: it spends the token budget on `reasoning_content`
  and returns `content: null`. Callers now size the *answer*; the client adds thinking
  headroom on top.
- Next.js 15.1.3 shipped with a CVE; upgraded to 15.5.25.
- A live API key was written into `backend/.env.example`, which is a **committed** file.
  Moved to `backend/.env` (gitignored) and the placeholder restored.

---

## Known gaps / next steps

- **Tamil speech recognition is the weak point.** Whisper mishears English
  loanwords inside Tamil: "வெல்டிங்" (welding) came back as "வெள்ளி" (silver), and
  extraction then reported *silver work* — correctly grounded in a transcript that
  was itself wrong, which is the one failure evidence verification cannot catch.
  Same at `medium` and `large-v3`, local and Groq-hosted, so it is the model
  family. IndicWav2Vec (Apache 2.0, not gated) is the Tamil-specific alternative.
  Not yet confirmed against real human speech rather than synthesised audio.
- **NER is built but unused.** `services/ner.py` tags PER/ORG/LOC and degrades to
  `[]` safely, but nothing calls it. It is meant to feed the location field and
  evidence spans. `ai4bharat/IndicNER` is also a gated repo and needs `HF_TOKEN`.
- **Local Whisper is slow on a laptop CPU** — ~53s per clip against ~1s on
  Groq-hosted Whisper, which is available under the same key already in use.
- **Audio retention is three-quarters wired.** The opt-in, the check constraint
  and the purge function are in place; nothing uploads a clip, so `audio_url` is
  only ever read and the passport's "Play" control has nothing to play.
- **Place names render in English inside non-English sentences** ("இது Salemலேயே
  இருக்கிறது"). Matching resolves them correctly; only the display label is
  untranslated. Fix with a place-name map alongside `DISPLAY_NAMES`.
- **`npm run lint` does not exist.** `next lint` was removed in Next 16 and eslint
  is not a dependency, so lint has never run on this project.
- **Rate limiting is per-process.** Behind multiple workers the effective limit
  multiplies; move the counter to Redis for a multi-instance deployment.
- **Application tracking is deferred** (PRD section 9). "I want this" reveals the
  scheme reference to quote in person rather than pretending to submit anything.

---

## Stack migration — 2026-09-10

Replaced the proprietary speech and LLM vendor with open-source components.
Every layer except the LLM now runs on the machine.

| Layer | Was | Now | Licence |
|---|---|---|---|
| Speech-to-text | Sarvam Saarika | faster-whisper `medium` int8 | MIT |
| Text-to-speech | Sarvam Bulbul | Piper (ta/hi/en) | MIT; Tamil voice CC-BY-4.0 |
| Extraction / explanation | Sarvam-105B | Groq-hosted `qwen/qwen3.8-27b` | Open weights, hosted |
| Embeddings | — | `multilingual-e5-base` | MIT (unchanged) |
| Entity tagging | — | `ai4bharat/IndicNER` | MIT, gated |

Notes worth keeping:

- **The model was chosen by measurement, not by name.** `llama-3.3-70b-versatile`
  had already been rotated out of Groq's lineup. Of the three real candidates,
  `qwen/qwen3.8-27b` was both the fastest (1.1s) and the only one to extract a
  skill the person *described* rather than named ("diagnosing engine problems by
  sound"). Groq rotates models: if `LLM_MODEL` 404s, list `/v1/models` and re-pick.
- **Extraction went from ~99s to ~1.9s**, which also retired the timeout problem —
  reasoning headroom is 0 and the timeout is 120s against a 2-second call.
- **There is no Tamil voice in the official Piper repository.** The one in use is
  `tinisoft/piper-ta_IN-rasa_female-medium`, trained on AI4Bharat Rasa, and it is
  CC-BY-4.0 — so the stack is not uniformly MIT, and shipping it obliges
  attribution.
- **Nothing about a person's voice leaves the process any more.** Audio is
  decoded, transcribed and dropped locally; only the transcript text reaches Groq.

---

## Fixed on 2026-09-10

- **Sarvam retired three model ids.** `saaras:v2` (STT) and `bulbul:v2` (TTS) were both
  rejected, and speaker `anushka` is incompatible with `bulbul:v3`. Now `saarika:v2.5`,
  `bulbul:v3`, `priya`. `saarika` over `saaras` deliberately: `saaras` translates to
  English, which would break the Tamil transcript the evidence check depends on.
- **The browser could never be transcribed.** MediaRecorder produces WebM/Opus; Sarvam
  accepts only mpeg/wav/pcm/aac/aiff. `lib/wav.ts` now converts to 16 kHz mono PCM in the
  browser before upload. Verified by running the shipped encoder against real speech.
- **`next build` was broken** — Next 16 removed the `eslint` key from `NextConfig`.
- **CORS allowed only port 3000.** Next silently increments to 3001 when 3000 is busy, and
  the resulting failure is indistinguishable from a dead backend. 3001/3002 now allowed.
- **An unreachable backend failed silently.** `health === null` disabled the mic with no
  message and no banner. `healthUnreachable` now says so in all three languages.
- **Session setters had unstable identities**, so screens listing them in effect deps tore
  down in-flight work and restarted it. All seven are `useCallback(..., [])`.
- **The test suite ran against the live database.** `conftest.py` popped `DATABASE_URL`,
  but Settings reads `.env` too, so a missing variable let the file's value through. It
  wrote 14 fixture sessions into production Supabase before this was caught.
- **`db/002_functions.sql` could not be applied at all.** `set search_path = ''` hides
  pgvector's `<=>`, because operators cannot be schema-qualified the way tables can.
  Now `operator(public.<=>)`.
- **Normalization never matched anything.** The taxonomy held hash-based vectors, so every
  skill scored 0.12-0.48 against a 0.60 candidate threshold. With `multilingual-e5-base`
  the same inputs score 0.78-0.90, and Tamil "இன்ஜின் சத்தம்... கண்டுபிடிக்கிறது" now
  reaches Engine Diagnostics at 0.836.
- **Every explanation silently fell back to templates.** The prompt was given 4500
  tokens; measured, Sarvam-105B needed 7.5k-9k to reason through it before answering.
  Raising `LLM_REASONING_HEADROOM` to 11500 fixed it. Superseded by the stack
  migration below: Qwen does not reason first, so the headroom is back to 0.
- **`LLM_TIMEOUT_SECONDS` was shorter than a real extraction** — 90s against a measured
  99s, so the call was cut off mid-answer and the screen waiting on it never filled.
  Raised to 240s, then relaxed to 120s once Groq brought extraction under 2s.
