# VoicePath — Build Status

> **This file is the live todo list.** It is updated every time a task is completed.
> Last updated: 2026-09-11 (schemes rename; RAG merged)

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

**Deployed and running.** Frontend on Vercel, backend on Render, database on
Supabase. Everything below is detail.

---

## How to run it

```bash
# Backend  (http://localhost:8000)
cd backend
pip install -r requirements-deploy.txt   # ~300MB: Piper, FastAPI, asyncpg
python -m app.scripts.fetch_voices       # Piper voices for ta/hi/en (~190MB)
uvicorn app.main:app --reload --port 8000

# Frontend (http://localhost:3000)
cd frontend && npm install && npm run dev
```

Two keys, both free: `LLM_API_KEY` (Groq — speech and LLM) and `HF_TOKEN`
(Hugging Face — embeddings). Text-to-speech runs in-process and needs neither.

`requirements-ml.txt` instead (~3GB, adds torch) runs speech recognition and
embeddings locally too — `STT_PROVIDER=local`, `EMBEDDING_PROVIDER=local`. Then
nothing but the LLM leaves the machine, at the cost of 32.5s per clip on a CPU
against 1.4s hosted.

`--reload` watches Python files, not `.env`. Changing a provider means a full
restart.

`README.md` has the full setup, including Supabase and the offline mode.

---

## Layout

As on `main`. Files marked **(rag)** exist only on the `rag` branch.

```
HACKATHON_PLAN.md          Seven-part jury narrative, running order, pre-flight
samplequestions.md         50 jury questions with grounded answers
README.md                  Setup, the stack and what it costs, known limits
STATUS.md                  This file
.python-version            3.11.9 -- Render defaults to 3.14, which has no wheel

db/                        Apply in numeric order
  001_schema.sql             9 tables, pgvector, constraints, FK indexes
  002_functions.sql          match_skill_taxonomy, scheme_skill_vectors,
                             purge_expired_audio
  003_seed.sql               44 skills, 16 Salem/Erode schemes. Idempotent
  004_policies.sql           RLS: catalogues public-read, personal data closed
  005_documents.sql          (rag) scheme_documents, document_chunks, retrieval fn

backend/
  Dockerfile                 For hosts that only take an image. Render uses the
                             build/start commands instead
  requirements.txt           API only (~10MB)
  requirements-deploy.txt    + Piper (~300MB). What the deployment installs
  requirements-ml.txt        + torch, Whisper (~1.16GB). Fully local operation
  app/
    config.py                Every provider setting, and the validator that
                             downgrades to offline rather than failing at request time
    main.py                  App wiring, CORS, /health
    data/catalogue.py        In-memory catalogue when there is no database
    models/schemas.py        Request and response shapes
    prompts/text.py          All four prompts, reviewable on their own
    routes/                  Thin -- speech, profile, schemes, sessions,
                             assistant, admin
    services/
      stt.py                 Whisper: groq | local | offline
      tts.py                 Piper, in-process. Falls back to the browser
      llm.py                 groq | gemini | offline behind one interface
      embeddings.py          e5: hf_api | local | offline hashing
      extraction.py          Skills from speech. _validate drops what it cannot
                             quote from the transcript
      normalization.py       Exact alias -> embedding -> LLM assist -> ask the user
      matching.py            Deterministic 50/25/15/10. Imports no LLM
      explanation.py         Grounded bullets. No field carries a score back
      assistant.py           Q&A over one scheme's stored fields only
      taxonomy.py            Vector search, alias index, localized labels
      ner.py                 IndicNER entity spans. Built, nothing calls it
      retrieval.py           (rag) Chunking and hybrid dense + keyword search
      scheme_qa.py           (rag) Answers that cite a passage, or refuse
      db.py, repository.py, schemes.py, pipeline.py, ratelimit.py
    scripts/
      embed_taxonomy.py      Taxonomy vectors. --all to recompute
      fetch_voices.py        Piper voices for ta/hi/en (~190MB)
      ingest_documents.py    (rag) PDF/text -> chunks -> embeddings
      migrate.py
  tests/                     178, fully offline -- no keys, network or database
  data/scheme_docs/          (rag) Source PDFs, committed (~2.1MB): PM-AJAY
                             and PMAGY guidelines, TN Sigaram Thodu EOI.
                             Public documents, kept so retrieval is reproducible

frontend/
  app/
    page.tsx                 Landing
    speak/                   Mic, live waveform off real amplitude
    understanding/           Editable skill cards, each showing its evidence
                             and now its confidence against the threshold
    understanding/disambiguate/   Low-confidence screen
    schemes/           Ranked feed
    schemes/[id]/      RSC detail + score bars with their weights
    passport/                Skill Passport, audio-retention toggle
    admin/                   Schemes, taxonomy, sessions (no transcripts)
  components/                SkillCard, Waveform, MatchRing, AskVoicePath, ...
  lib/
    api.ts                   Typed client. Errors carry the backend's own words
    session.tsx              Session state; health with retry and backoff
    i18n.ts                  ta/hi/en copy, written in each language
    recorder.ts              getUserMedia, MediaRecorder, live levels
    wav.ts                   WebM/Opus -> 16kHz mono WAV, in the browser
    browser-speech.ts        On-device recognition and synthesis fallback
```

---

## Task checklist

### Phase 0 — Scaffold & docs ✅
- [x] Directory tree
- [x] `STATUS.md` (this file)
- [x] `README.md` — setup, the pipeline, the three enforced rules
- [x] `.gitignore` — `.env` protected before any key was written

### Phase 1 — Database ✅
- [x] `db/001_schema.sql` — 9 tables, pgvector, constraints, FK indexes
- [x] `db/002_functions.sql` — `match_skill_taxonomy`, `scheme_skill_vectors`, `purge_expired_audio`
- [x] `db/003_seed.sql` — 44 skills + 16 Salem/Erode schemes + localized labels
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
- [x] `services/schemes.py`, `services/repository.py`, `models/schemas.py`

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
- [x] `/schemes` — ranked feed, reasons weighted equal to titles
- [x] `/schemes/[id]` — RSC detail + score bars + Ask VoicePath

### Phase 8 — Admin ✅
- [x] `/admin/schemes`, `/admin/taxonomy`, `/admin/sessions` (read-only, no transcripts)

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
- Ranked 16 schemes; top match 100%, location scored 1.00
- Explained in Tamil: *"நீங்கள் வெல்டிங் செய்கிறீர்கள் — இந்த வேலை அதுவே."*
- Answered *"எனக்கு சான்றிதழ் இல்லை. பிரச்சனையா?"* from the listing, in Tamil

---

## Decisions & assumptions

1. **Runs with zero API keys, but does less.** Every provider has an offline
   implementation and the app downgrades automatically, never silently: `/health`,
   response bodies and a UI banner all say so. The deployed configuration does use
   keys — one for Groq (speech and LLM) and one for Hugging Face (embeddings) —
   because the offline extraction path only finds skills a person *names*, not
   ones they *describe*, which is most of the value.
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
   re-running `embed_taxonomy --all`. Without `--all` the script only fills in
   missing rows and leaves stale vectors in place, which fails silently: both
   models emit 768 valid-looking floats and only the match quality tells you.
9. **Vectors must come from one model.** `hf_api` and `local` run the same
   `multilingual-e5-base` and are interchangeable — measured cosine 1.0000. The
   `offline` hashing provider is not comparable with either, so switching to it
   after embedding corrupts every comparison rather than degrading it.

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

## Deployed

| Layer | Where | Notes |
|---|---|---|
| Frontend | Vercel | `NEXT_PUBLIC_API_BASE_URL` points at Render |
| Backend | Render free tier | Sleeps after ~15 min idle; ~30s to wake |
| Database | Supabase | Reached through the **pooler**, not the direct host |
| Speech, LLM | Groq | Whisper large-v3 and `qwen/qwen3.8-27b` |
| Embeddings | HF Inference API | Same `multilingual-e5-base` as the stored vectors |
| TTS | In the container | Piper, ~270MB of the ~300MB image |

Running cost: nothing. Every tier in use is free.

`CORS_ORIGINS` must name the Vercel origin exactly. When it does not, the browser
discards every response and the failure is indistinguishable from a dead server.

---

## Known gaps / next steps

- **Tamil speech recognition is the weak point.** Whisper mishears English
  loanwords inside Tamil: "வெல்டிங்" (welding) came back as "வெள்ளி" (silver), and
  extraction then reported *silver work* — correctly grounded in a transcript that
  was itself wrong, which is the one failure evidence verification cannot catch.
  Same at `medium` and `large-v3`, local and hosted, so it is the model family.
  Hindi and English are unaffected. IndicWav2Vec (Apache 2.0, not gated) is the
  Tamil-specific alternative.
- **RAG is built but unmerged.** `rag` branch: 148 chunks from three real scheme
  PDFs, hybrid dense + keyword retrieval, answers that cite a passage or refuse.
  Service layer only — no route, no UI. Deliberately never touches matching.
- **NER is built but unused.** `services/ner.py` tags PER/ORG/LOC and degrades to
  `[]` safely; nothing calls it, and `transformers` is not in the deploy set, so
  `/health` reports it offline.
- **Only 16 schemes, seeded.** data.gov.in publishes district catalogues
  under GODL-India; the schema and admin importer already fit.
- **Audio retention is three-quarters wired.** Opt-in, check constraint and purge
  function exist; nothing uploads a clip, so the passport's "Play" has nothing to
  play.
- **Place names render in English inside non-English sentences.** Matching
  resolves them correctly; only the display label is untranslated.
- **`npm run lint` does not exist.** `next lint` was removed in Next 16 and
  eslint is not a dependency.
- **Rate limiting is per-process.** Multiplies behind multiple instances; move
  the counter to Redis before scaling.

---

## Fixed on 2026-09-11

- **Renamed the core entity from `opportunities` to `schemes`.** 540 references
  across 38 files, plus the tables, routes and frontend directories. `db/006`
  moves the tables in place rather than rebuilding them, so no row is lost and
  no id changes.
- **Added `official_url`**, the government's own page for a scheme, validated as
  an absolute http(s) URL at the edge and by a check constraint. Distinct from
  `source_reference`, which is a code to quote at an office. The assistant
  quotes it verbatim and says so plainly when the record has none —
  `tests/test_official_url.py` asserts it never constructs one.
- **The admin dashboard writes.** `/admin` was a 404; it is now an index, and
  schemes can be created, edited and deactivated. The endpoints already existed;
  the frontend was a read-only table.
- **The delete endpoint deactivates rather than deletes**, so the audit trail
  survives. The button says so, and offers Reactivate. That needed `is_active`
  carried through the service and schema, which nothing exposed before.
- **RAG merged to `main`** (PR #1). Retrieval over scheme documents, unused by
  any route; `TODO: RAG integration` marks the two call sites.

- **Deployed the whole stack on free tiers.** Python pinned to 3.11 (Render
  defaults to 3.14, for which `pydantic-core` publishes no wheel and the Rust
  build fails on a read-only Cargo registry).
- **`.gitignore` was silently excluding source.** The Piper voice pattern was a
  bare `models/`, which git matches at any depth — so `backend/app/models/` never
  got committed and the deploy crashed on `ModuleNotFoundError: app.models`.
  Both patterns anchored; swept the tree for others.
- **Transcription moved to Groq.** Local CPU Whisper measured 32.5s on a 5.8s
  clip — 5.6x slower than realtime. Hosted: 1.4s. Same open weights;
  `STT_PROVIDER=local` still works for an air-gapped deployment.
- **Embeddings moved to the HF Inference API**, dropping torch and taking the
  image from ~1.16GB to ~300MB, which is what fits a 512MB tier. Verified
  interchangeable with the local model at cosine **1.0000**, so the stored
  taxonomy vectors stayed valid and nothing needed re-embedding.
- **The health check now retries.** A free tier sleeps when idle, so a single
  failed call reported "unreachable" about a server that was merely waking.
  Six attempts with backoff, and screens say "starting up" until they are spent.
- **Spoken answers kept playing after leaving the screen.** `playBase64Audio`
  built a detached `Audio` element nothing held, and the cleanup only cancelled
  `speechSynthesis`. Also unblocked the spinner, which waited for audio to finish
  before admitting the answer had arrived.
- **Language switching did not re-explain.** Explanations were generated in
  `session.language_detected` and stored, so a Hindi reader saw Tamil reasons.
  Matching now takes a language and the page re-requests on toggle — affordable
  only because `explain_many` went from sequential to four at a time.
- **Confidence and weights are now visible.** Skill cards show
  `0.836 - accepted - needs 0.82`; score bars carry `x50%`, `x25%` and the full
  formula. Both already computed, neither previously shown.

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
