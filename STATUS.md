# VoicePath — Build Status

> **This file is the live todo list.** It is updated every time a task is completed.
> Start at **To-do** — that is the working checklist. **Next up** carries the
> detail behind the top items; everything below it is the record of the build.
> Last updated: 2026-09-12 (matching scored everything 86-95; fixed. 254 tests)

**Project root:** `C:\Users\Sai Dixit\voicepath`
**Sources:** `PRD_File_For_Project.md` (spec) · `VoicePath Mockups.html` (design canvas, unpacked)

---

## To-do

> **This checklist is the live task list, kept current from 2026-09-11 onward.**
> Tick an item the moment it is done and move its detail into a `Fixed on …`
> section below. Add new items here as they are found, rather than in prose.
> Completed work is not deleted from the file — it moves down, so the history
> of what was built stays readable.

### Deploy order — read before merging anything that touches `db/`

**Apply the migration before the code that needs it reaches production.**
Render redeploys on a push to `main`, and Supabase does not. On 2026-09-12
PR #2 merged code that selects and inserts `matches.explanation_language`
while the column existed only in `db/007_match_language.sql`. Every route
touching a match returned 500 — `/schemes` among them, which is the screen
the whole product leads to. `/health` stayed green throughout, because it
never reads that table, so nothing announced the breakage.

The order that works:

```bash
cd backend && python -m app.scripts.migrate --only 007   # first
git push origin main                                     # then
```

Every file in `db/` is idempotent, so applying early is free and applying
twice is harmless. There is no cost to doing this in the safe order.

- [ ] **`/health` does not notice a schema it cannot use.** It reports the
      database as connected because it is; the column the code needs is a
      different question. A cheap check — select the newest column the code
      depends on — would have turned a silent outage into a red banner.

### Now — correctness, and the largest spec gaps

- [ ] **Two live schemes still have no required skills.** `Pharma Business`
      (18) and `Plumbing Works` (19) were created before the admin form had a
      skills field, so they score the neutral 0.5 for everyone and sit above a
      real mismatch. The form can fix them now; the rows themselves were left
      alone because choosing which skills a scheme needs is a decision about
      the catalogue, not a bug fix.
- [ ] **The spec disagrees with itself about the weights.** §14 lists Skill 40
      / Education 20 / Experience 15 / Location 15 / Other 10; §4.4 and §8 give
      the 50 / 25 / 15 / 10 the code implements, and there is no education
      term anywhere. Worth settling before a jury asks which is authoritative.

- [ ] **Tamil speech recognition.** Whisper mishears English loanwords inside
      Tamil: "வெல்டிங்" (welding) → "வெள்ளி" (silver), and extraction then
      reported *silver work*, correctly grounded in a transcript that was itself
      wrong. Try constrained decoding over the 44 taxonomy terms first, then a
      phonetic fallback in normalisation; route Tamil to AI4Bharat
      IndicWav2Vec only if neither lands. Detail under **Next up → 4**.
- [ ] **Jobs and Training as their own entities.** `voice_condensed.md` §12–§13
      describe three data models; everything is a `scheme` with a `type` column,
      so the All/Jobs/Schemes/Training filter has nothing to filter on. Touches
      `db/` (two tables + migration), `models/schemas.py`, `services/`,
      `routes/`, the admin dashboard and `matching.py` — the per-type scoring
      weights are the part to think about. Half a day or more.

### Next — cheap wins that make the build look finished

- [x] **Admin overview metrics** (§18) — done 2026-09-12. `GET
      /api/admin/overview` behind a stat row on `app/admin/page.tsx`.
- [ ] **Filters on the scheme list** (§17): location, skill, experience, type.
      `services/schemes.py` already filters by district, so the query shape
      exists; mostly `app/schemes/page.tsx` plus query parameters on the list
      route. Do it after Jobs/Training — the type filter is most of the point.
- [ ] **Place names render in English inside non-English sentences.** Matching
      resolves them correctly across scripts; only the display label is
      untranslated. The last known language leak, now that the rest are
      closed -- see *Fixed on 2026-09-11*.
- [ ] **An error already on screen does not follow a language switch.**
      Failures are stored as rendered strings, so the sentence shown keeps
      the language it was written in. Storing the cause and deriving the
      message at render time would fix it, across six files' error paths.
      Narrow and transient, which is why it was left rather than bundled
      into the language fix.
- [ ] **`npm run lint` does not exist.** `package.json` still points at
      `next lint`, which Next 16 removed, and eslint is not a dependency. Either
      add eslint properly or drop the script so it stops lying.
- [ ] **The motion layer has not been seen in a browser.** It compiles, `/`
      still prerenders, and every rule degrades under `prefers-reduced-motion`
      — but no screenshot was taken, because this environment has no browser.
      Worth one look on a real phone before it is shown to anyone.

### Later — scale, breadth and loose ends

- [ ] **NER is built but unused.** `services/ner.py` tags PER/ORG/LOC and
      degrades to `[]` safely, but nothing calls it and `transformers` is not in
      the deploy set, so `/health` reports it offline. Wire it into extraction
      or delete it — a built-and-unused service is the worst of both.
- [ ] **Audio retention is three-quarters wired.** Opt-in, check constraint and
      purge function exist; nothing uploads a clip, so the passport's "Play" has
      nothing to play.
- [ ] **Only 16 schemes, seeded.** data.gov.in publishes district catalogues
      under GODL-India, and the schema plus admin importer already fit.
- [ ] **Retrieval still cannot reach matching.**
      `tests/test_assistant_routing.py` asserts the separation by reading
      `matching.py`'s source rather than its imports, which is weaker than it
      looks. Tighten the assertion.
- [ ] **Rate limiting is per-process.** It multiplies behind multiple
      instances; move the counter to Redis before scaling past one.
- [ ] **Confirm `TAVILY_API_KEY` is set in the deployed environment.** Without
      it the web-search widening silently does not run and the corpus answers
      only what it holds — which is correct behaviour, but not the intended one.

---

## Next up

Four things, ordered by what they give back for the work. Enough detail here to
pick any of them up cold, in a new session or on a different machine.

### 1. Jobs and Training as their own entities

`voice_condensed.md` §12 and §13 describe jobs, schemes and training as three
data models. Everything is currently a `scheme` with a `type` column, which is
why the All/Jobs/Schemes/Training filter in §17 has nothing to filter on.

Touches: `db/` (two new tables + migration), `models/schemas.py`,
`services/`, `routes/`, the admin dashboard, and `matching.py` — the scoring
weights differ per type, which is the part to think about rather than type out.

Half a day or more. The largest remaining gap between the spec and the build.

### 2. Admin overview metrics

§18 asks for totals per opportunity type, active and expired counts, total
users, searches today, and popular skills, locations and searches. `/admin` is
currently navigation cards with no numbers.

Every figure already exists in the database. This is a handful of aggregate
queries behind one new admin endpoint, plus a stat row on `app/admin/page.tsx`.
Nothing here is hard; it is the cheapest way to make the dashboard look like one.

About 90 minutes.

### 3. Filters on the scheme list

§17: location, skill, experience, type. `services/schemes.py` already filters by
district, so the query shape exists; this is mostly `app/schemes/page.tsx` plus
query parameters on the list route.

Half a day. Worth doing after (1), since the type filter is most of the point.

### 4. Tamil speech recognition

The known correctness problem, and the one a jury is most likely to find.
Whisper mishears English loanwords inside Tamil — "வெல்டிங்" (welding) came back
as "வெள்ளி" (silver) and the pipeline reported *silver work*, correctly grounded
in a transcript that was itself wrong.

Four approaches, in order of effort:

1. Route Tamil to AI4Bharat IndicWav2Vec (Apache 2.0, not gated) and leave
   Hindi and English on Whisper. `services/stt.py` already dispatches by
   provider, so this is a third branch.
2. Constrained decoding over the 44 taxonomy terms. We know the vocabulary that
   matters; biasing the decoder toward it makes the right word likelier without
   changing models at all.
3. Phonetic fallback in normalisation — "வெள்ளி" and "வெல்டிங்" are close in a
   transliteration, and edit distance would catch what cosine similarity does not.
4. Fine-tune on Common Voice Tamil (CC0).

(2) and (3) need no new model and are the better first attempt.

---

## Progress

| Phase | Status |
|---|---|
| 0. Scaffold & docs | ✅ Done |
| 1. Database (schema + seed) | ✅ Done |
| 2. Backend core (config, db, providers) | ✅ Done |
| 3. Backend pipeline (extract → normalize → match → explain) | ✅ Done |
| 4. Backend routes + rate limiting | ✅ Done |
| 5. Backend tests | ✅ Done — **254 passing**, 7 skipped |
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

As on `main`.

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
  005_documents.sql          scheme_documents, document_chunks, retrieval fn
  006_schemes_rename.sql     opportunities -> schemes, in place. No row lost
  007_match_language.sql     which language a stored explanation is in
  008_drop_compatibility_views.sql
                             retires the opportunities shims 006 left behind

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
                             assistant, query, admin
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
      retrieval.py           Chunking and hybrid dense + keyword search
      scheme_qa.py           Answers that cite a passage, or refuse
      intent.py              Work, question, or both -- decides the route
      websearch.py           Official sources when the corpus falls short.
                             Consults no model, so it cannot invent a URL
      db.py, repository.py, schemes.py, pipeline.py, ratelimit.py
    scripts/
      embed_taxonomy.py      Taxonomy vectors. --all to recompute
      fetch_voices.py        Piper voices for ta/hi/en (~190MB)
      ingest_documents.py    PDF/text -> chunks -> embeddings
      migrate.py
  tests/                     261, fully offline -- no keys, network or database.
                             254 pass; 7 skip without one (intent topic check)
  data/scheme_docs/          Source PDFs, committed (~2.1MB): PM-AJAY
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

### Phase 5 — Backend tests ✅ (254 passing, 7 skipped)
- [x] `test_matching.py` — weights, determinism, each component, grounding
- [x] `test_extraction.py` — evidence grounding in ta/hi/en, invention rejected
- [x] `test_normalization.py` — alias matching across scripts, no silent upgrades
- [x] `test_explanation.py` — cannot re-rank, no eligibility promises, no jargon
- [x] `test_places.py` — Tamil/Hindi/English place names and case endings
- [x] `test_localization.py` — every skill has ta/hi labels; sentences stay in one language
- [x] `test_catalogue_sync.py` — SQL and Python catalogues cannot drift
- [x] `test_api.py` — full pipeline, privacy invariants, admin gate
- [x] `test_intent.py` — work / question / both, in three languages, and noise claiming nothing
- [x] `test_websearch.py` — domain trust by scheme *and* host; URLs are never constructed
- [x] `test_official_url.py` — the assistant quotes the stored URL or says there is none
- [x] `test_assistant_routing.py` — retrieval cannot reach matching
- [x] `test_language_switching.py` — a stored match re-reads in any language, scores unmoved
- [x] `test_admin_gate_messages.py` — unconfigured is 503; a wrong token never reveals how the deployment is set up
- [x] `test_admin_overview.py` — the figures add up, and carry no transcript or question text
- [x] `test_matching_relevance.py` — a mismatch scores low, and a skill-less scheme cannot top the list

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
- [x] `pytest` — 254 passed, 7 skipped (the 7 need a database)
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
- **RAG answers scheme questions, and nothing else.** 148 chunks from three real
  government PDFs. A question with no recognised listing intent goes to the
  guidelines; anything about the row in front of the person does not. Retrieval
  still cannot reach matching, and `tests/test_assistant_routing.py` asserts it
  by reading `matching.py`'s source rather than its imports.
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

## Fixed on 2026-09-12 — every scheme scored 86-95, whatever you said

Reported from the deployed app: *"I was a carpenter for 3 years"* returned
Pharma Business **95**, Plumbing Works **95**, a welding course **91** — while
the explanations underneath correctly said there was no connection between
carpentry and any of them. The reasoning knew; the number did not.

Reproduced exactly against the live catalogue. **Extraction and normalization
were never at fault** — "carpenter" resolved to `Carpentry (SK042)` at
confidence 1.0. Both defects were in `matching.skill_similarity`.

**A scheme that asks for nothing scored full marks.** It returned 1.0 when
`required_skills` was empty, reasoning that "nothing asked for cannot be
unmet". Fair while every scheme was seeded with its skills; false the moment
the admin form created one. Both 95s were admin-created schemes with zero
requirements, and such a scheme always leads: 0.50 + 0.25 + 0.15 + 0.05 = 0.95.
Asking for nothing is the absence of evidence, so it now takes `SKILL_UNKNOWN`
= 0.5, the same neutral value an unknown location and unknown experience use.

**The similarity floor sat far below the model's noise floor.** Measured over
this taxonomy with `multilingual-e5-base`, cosine from Carpentry to all 22
required skills in the catalogue runs **0.853 to 0.921** — a spread of 0.068,
with Retail Sales (0.918) essentially tied with Welding (0.921). There is no
signal in that band. A real relationship separates cleanly above it:
Two-Wheeler Repair scores **1.000** against itself and **0.947** against
Four-Wheeler Repair, then drops to 0.84-0.89 for everything else.

The code admitted anything over **0.55** and paid `weight × similarity`, so an
unrelated trade collected 85-92% of the weight. Similarity is now rescaled
linearly from a measured floor of 0.92, so the noise band pays nothing. This is
the same narrow-band property already documented for retrieval, where
"asdfghjkl" scores 0.794 against the corpus — one model, one weakness, two
places it had to be handled.

Measured before and after, against the live catalogue:

| input | before | after |
|---|---|---|
| carpenter, 3 years | Pharma 95, Plumbing 95, Welding 91 | Pharma 70, Plumbing 70, rest 45 |
| two-wheeler mechanic, 6 years | — | **Two-Wheeler Training 79**, Two-Wheeler Technician 73, Workshop Setup 67 |

**The root cause was in the admin form, and is closed too.** The API always
accepted `skill_ids` and `create_scheme` always wrote them; the form sent
`skill_ids: []` unconditionally, so every scheme created through the UI was
skill-less by construction and the scoring fix alone would have been undone by
the next one. The form now has a skill picker, editing carries existing skills
through rather than stripping them, and choosing none says plainly what that
costs.

A naming change worth knowing: a requirement is only listed as *matched* —
which is what an explanation may claim about a person — when the rescaled
credit clears 0.5. Partial credit still moves the score below that; it is
simply not something to say out loud.

---

## Done on 2026-09-12 — the public screens have motion, and admin moved to the navbar

Asked for directly: *"it looks bland and boring, can you add any animations?"*
plus a specific request to move the admin link out of the landing page's footer
and into the navbar beside the language toggle. Both done.

**The palette and the type did not change.** The muted green chosen explicitly
against a saturated "AI product" hue, amber rather than red for uncertainty,
Anek so a Tamil headline carries an English one's weight — that is the one
genuinely opinionated thing here, and swapping it for something livelier would
have made the product *more* generic, not less. The blandness was never the
colours; nothing on the page was alive.

**The boldness is spent in one place: the microphone.** The most characteristic
thing in this product's world is a voice becoming legible, and the mic was a
green circle with a single pulsing border. It now has two rings half a cycle
apart, so it reads as sound leaving the mic rather than a border that throbs;
they quicken on hover and focus; the button takes a real press; and a soft
radial field sits behind it so it rests in something rather than floating on
flat cream.

Everything else stays quiet, deliberately:

- **One orchestrated entrance, on the landing only.** Statement, then mic, then
  the other two languages, each naming its own delay where the element is
  written. Fade-and-slide on every section of every screen is the generic tell
  and was avoided.
- **`MatchRing` fills from empty once, on arrival.** The ring is the only place
  a score appears as a quantity rather than a numeral, and watching it stop
  somewhere is what makes 62% and 97% feel different to someone who does not
  read the digits.
- **Interaction motion everywhere else** — rows lift and press, nothing moves
  on its own.

**The hover rewrite is an accessibility fix wearing a polish hat.** Six
`onMouseEnter` handlers mutated `style.borderColor` and `style.color`, which
meant a keyboard user got no feedback at all — JavaScript hover has no focus
equivalent. They are now `.vp-row`, `.vp-row-accent` and `.vp-icon-button`,
so `:focus-visible` comes free. This was already on the to-do list from the
design review; it arrived with the motion because the same rules carry both.

Caught in self-review before commit: the delayed second ring began at full
opacity, so it would have sat on screen as a static circle for 1.8 seconds
before its turn — a bug that reads as a design choice. The keyframe starts at
zero now, with `backwards` fill so the delay holds an invisible frame.

`prefers-reduced-motion` still neutralises all of it through the existing
global rule; every entrance uses `both` fill, so nothing can be left invisible
when the animation is collapsed.

**Not verified in a browser.** It compiles, `/` prerenders, and the rules are
sound, but this environment has no browser and no screenshot was taken.

---

## Done on 2026-09-12 — /admin has its numbers

§18, and the cheapest item on the list. `/admin` was three navigation cards, so
the question an operator actually arrives with — *is anything happening?* — had
no answer on the page. Every figure was already in the database; nothing was
counting them.

`GET /api/admin/overview` returns the catalogue (total, active, deactivated,
and a breakdown by type), activity (sessions and questions, each with a today
count, plus a language split), the corpus (documents and indexed passages), and
what is common (top skills and places). A stat row and four small breakdowns
render it, in admin's deliberately plain style rather than the beneficiary
surface's.

Two things it will not do:

- **It reports no transcript and no question text.** `/admin/sessions` already
  refuses to show what people said about their own lives, and an aggregate is
  not a loophole for that. Skills are counted by their **taxonomy name**, never
  by `raw_name` — a raw name is the person's own words — so a skill that never
  normalized is left out rather than reported in someone's own phrasing. A test
  asserts the fixture transcript's words cannot appear in the response.
- **The popular lists are bounded at ten.** An unbounded "popular" list is a
  dump of the table wearing a summary's name, and on a busy deployment it is
  also a slow query.

It works without a database, from the in-memory store, because the admin
surface is reachable in offline mode and a dashboard that 503s there is worse
than one showing zeros honestly. That also meant the SQL path was **not**
covered by the suite, which runs offline — so it was executed directly against
the production schema before this was called done: 18 schemes, 58 sessions, 121
passages, totals reconciling.

---

## Fixed on 2026-09-12 — the admin gate now says when it cannot authorise anyone

`"Not authorised."` answered three different situations, and one of them is not
an authorisation failure:

1. a wrong token, when real admins are provisioned
2. a wrong token, when only a bootstrap token is configured
3. no admin users *and* no bootstrap token — **the server cannot accept any
   token from anyone**

(3) is a configuration fault wearing an authorisation error's clothes, and it
is expensive: an operator types correct-looking tokens into `/admin/schemes`
and nothing on screen can tell them the server was never able to accept one.
It answers **503** now, naming both `ADMIN_BOOTSTRAP_TOKEN` and `admin_users`,
which matches how `_require_database` already reports "admin needs something
this deployment has not been given".

**(1) and (2) stay byte-identical to each other**, and a test asserts the
refusal leaks none of `bootstrap`, `admin_users`, `provision` or `no admins`.
Telling them apart would reveal whether admins have been provisioned, which is
a fact about the deployment an unauthenticated caller has no business learning.
The distinction added here is *configured vs not*, never *provisioned vs not*.

Found on the way, and fixed with it: **the suite was reading the real
bootstrap token out of `backend/.env`** — the same leak already fixed for
`DATABASE_URL`, and for the same reason, since Settings reads the file as well
as the environment. The admin gate was therefore tested one way on a machine
with a `.env` and another way on CI. `conftest.py` pins an obviously-fake
value, which is also what makes "wrong token" and "not configured" two
reproducible states rather than an accident of the developer's filesystem.

No frontend change: both `AdminTable` and `/admin/schemes` already render the
response's `detail`, so the new sentence reaches the screen as written.

---

## Fixed on 2026-09-12 — the Supabase advisor's two ERROR findings

`security_definer_view` on `public.opportunities` and
`public.opportunity_skills`. Both are the read-only shims `006` created during
the rename, and `006` says in as many words to drop them once the new code
shipped. It shipped; they stayed.

The finding is real, not linter noise. **A Postgres view runs as its owner
unless it is created `with (security_invoker = on)`.** These were not, and
their owner is `postgres` — so every read through `opportunities` was
evaluated with the owner's privileges and bypassed row level security on
`schemes` entirely.

Nothing was exposed by it. `schemes` and `scheme_skills` both carry a
public-read policy, so the rows reachable through the view were rows anyone
could already select. The danger was latent: the day either policy narrows,
the view would have gone on serving what the policy had just withdrawn —
silently, from a name no code references any more.

`db/008` drops both views and the `opportunity_skill_vectors` shim. Dropping
rather than recreating them with `security_invoker`, because they exist only
to serve code that no longer runs. Verified first that no reference to
`opportunit%` survives anywhere in `backend/`, `frontend/` or `db/` outside
`006` itself.

Audited the rest of the schema while there:

- No views remain in `public`, so the finding cannot recur from another one.
- RLS is enabled on all 12 tables.
- Five project functions, all with `search_path=""` pinned. One,
  `purge_expired_audio`, is `SECURITY DEFINER` — deliberately, since it must
  delete audio regardless of caller — and being pinned it is not the
  `function_search_path_mutable` hazard. Correct as written.

Applied to production and smoke-tested: `/health` connected, 18 active
schemes, `/api/schemes` 200.

---

## Fixed on 2026-09-12 — the schemes page could not load in production

Reported as *"Could not reach VoicePath. Check that the backend is running."*
on `voicepath.vercel.app/schemes`. The backend was running.

`/health` returned 200 in 0.29s with the database connected and 17 active
schemes, so the banner was misleading: it is the health-retry message, and a
free tier waking from sleep produces it too. The real failure was underneath.

Reading a stored match returned **500 where it should have returned 404** —
`select ... explanation_language from matches` against a column that did not
exist. PR #2 merged the code that depends on `db/007_match_language.sql`; the
migration had never been applied to Supabase.

Applied it with `python -m app.scripts.migrate --only 007`. Verified:

- the probe that returned 500 now returns 404 with *"This scheme has not been
  matched for that session."*
- `matches.explanation_language` is `text`, nullable, with the check
  constraint restricting it to `ta`/`hi`/`en` or null
- all 106 pre-existing rows are null, which is what the nullable column was
  for: they hold prose in an unknown language and correctly force a rewrite
- a full run — transcript, extract, match, then the same match read in Tamil —
  returns 200 at every step, and new rows store `en`

Nothing in the application code was wrong. The lesson is in **Deploy order**,
at the top of the to-do list.

---

## Fixed on 2026-09-11 — language switching

Switching language left parts of a screen in the previous one. Five separate
leaks, two root causes, found by tracing every source of text on screen rather
than by patching the first one that showed.

**Root cause 1: server-written prose was cached and never re-requested.**
Static copy re-renders from a table the instant `language` changes. Explanations
and retrieval answers are *prose the server wrote in one language*, and
`setLanguage` only swapped a field. Exactly one screen compensated -- `/schemes`
kept an `explainedIn` ref -- so everywhere else kept the old language.

- **The stored explanation could not change language at all.** `matches` had no
  column recording which language its prose was in, so nothing could tell the
  text was stale, and `GET /{id}/match/{session}` had no way to ask for another.
  `db/007` adds `explanation_language`, nullable on purpose: rows written before
  it exist in an unknown language, and a null correctly forces a rewrite rather
  than asserting something the code would then trust.
- **Re-explaining does not re-score.** `_reexplain` rebuilds the grounding the
  explanation layer needs -- it is derived, not stored -- then writes the stored
  scores back over the recomputed ones before explaining. If the catalogue moved
  since the match was persisted, the numbers stay the audited ones and only the
  wording is new. An explanation has never been allowed to move a score, and
  translating one must not become the exception.
- **`explainedIn` was a local ref, so only its own screen benefited.** The
  language now lives beside the matches in session state as `matchesLanguage`,
  which is what lets the detail screen notice the same staleness.
- **The retrieval answer on `/understanding` was pinned by a boolean.**
  `asked.current` said "already asked" and so fixed the answer in the language
  it was first asked in. It holds the language now, and a change re-asks.
- **Past answers in Ask VoicePath are deliberately *not* re-translated.** A
  conversation is a record, and silently rewriting what was already said is
  worse than leaving it. But each line now carries the language it was written
  in, because tagging Tamil prose `hi` picks the wrong font and makes a screen
  reader mispronounce it.

**Root cause 2: strings that never entered the i18n layer.** These were not
stale; they were permanently English whatever was chosen.

- `"Something went wrong."` was hardcoded in **10 places**, across every
  user-facing screen -- an English sentence handed to a Tamil speaker at the one
  moment they were already confused.
- `payLabel` wrote `"up to ₹8,000"` inside otherwise Tamil rows.
- **`typeLabel` already existed, fully translated into Tamil and Hindi, and was
  called from one place out of four.** The scheme type rendered raw everywhere
  else. Partial adoption of a working helper, which is why the symptom looked
  arbitrary.
- Taxonomy categories rendered raw on skill cards; `categoryLabel` now covers
  all eleven.

`tests/test_language_switching.py` pins it: the same stored match read in Tamil
and in Hindi comes back in Tamil script and Devanagari, with the scores, the
breakdown and the rank byte-identical to the English read. It failed on the
first two assertions before the fix.

---

## Fixed on 2026-09-11

- **Web search over trusted sources** (spec sections 7, 8, 18, 19, 20). When
  nothing ingested can answer a question, official pages are searched, fetched
  and put through the same pipeline as a PDF — chunk, embed, retrieve, cite.
  How an answer is produced did not change; only how a document arrives.
  Needs `TAVILY_API_KEY`; without one the corpus answers what it holds and the
  widening simply does not run.
  - **Trust is the domain's, not the content's.** Only `.gov.in`-family pages
    are answerable straight away. Anything else is stored as
    `pending_verification` and retrieval will not read it until an admin
    decides, so searching the web cannot quietly widen what the system asserts.
    `/api/admin/sources` lists them; verify and reject are one call each, and a
    re-fetch does not re-open a rejected source.
  - **URLs are never constructed.** No model is consulted in
    `services/websearch.py` at all, which is the strongest form of section 8's
    rule: there is nothing there to generate one with. A result whose URL is not
    already absolute http(s) is dropped rather than repaired.
  - Searching happens only after the local corpus has failed, results are cached
    for 24h, and an unreachable API falls back to what is stored.
  - A test caught `ftp://gov.in/x` being trusted — tiering read the host and
    ignored the scheme. Lookalikes like `gov.in.example.com` were already
    handled by anchoring the match on a dot.
  - **A page that did not render must not be stored as policy.** myscheme.gov.in
    is a single-page app: it returns "Something went wrong. Please try again
    later." to our crawler *and* to Tavily's, at 616 characters — long enough to
    pass a length check and be ingested as a document. Pages are now judged on
    vocabulary rather than length; the shell has 53 distinct words, a real page
    has 371. It is excluded from search entirely, since every slot spent on it
    comes back empty, while staying trusted if a page ever arrives another way.
  - Verified end to end: "What is the PM Vishwakarma scheme?" was unanswerable
    from the PDFs, and is now answered from `pmvishwakarma.gov.in` with the URL
    cited.

- **A scheme name typed on its own now finds the scheme.** "pm ajay",
  "adarsh gram", "pm ajay skill development" were classified as neither work nor
  a question and fell through to "I did not catch any work you have done". People
  type search terms, not sentences; a bare name is a request to be told about it.
- **Similarity cannot tell a search term from noise, and never could.** e5 packs
  everything into a narrow band: "asdfghjkl" scores **0.794** against this corpus,
  above the 0.74 bar, while a legitimate Tamil question scores **0.769**. Raising
  the threshold would have cut the Tamil question and kept the gibberish. What
  separates them is whether the words appear in the documents at all —
  `retrieval.mentions()` asks exactly that, over content words only, since the
  corpus is indexed with the `simple` config and "there" in "hi there" otherwise
  matches a document that says "there" constantly.

- **Query understanding decides the route** (spec section 6). `POST
  /api/query/understand` reads one utterance and says whether it describes work,
  asks a question, or both. Before this the route was inferred from extraction
  finding nothing, which could not see the third case at all: "I do welding, is
  there a scheme for that?" produced a skill, so the question was never asked.
  Both halves are answered now.
- **A mixed question keeps its context.** The classifier returns the question in
  the person's own words, but a slice loses its own subject -- "is there a scheme
  for that?" cannot say what *that* was. When the sentence also describes work,
  the whole sentence goes to retrieval. Measured: the slice returned a vague yes,
  the whole sentence returned "the passages do not mention a specific scheme for
  welding", which is the true answer.
- **The classifier cannot assert anything.** It routes; extraction still verifies
  every quote against the transcript and retrieval still cites a passage or
  refuses. A wrong route sends someone to a step that finds nothing, which is
  recoverable. `tests/test_intent.py` covers the three languages, the both case,
  and the one that matters most -- noise claiming nothing.

- **Wired retrieval into the assistant.** It was merged and unused. A question
  with no recognised intent — "who is eligible?", "what documents do I need?" —
  now goes to the published guidelines and comes back with the document and
  section it was drawn from, shown under the answer. A question about the
  listing still answers from the row, because pay and distance are facts about
  one record and a policy paraphrase would be worse. Verified across the split:
  "how much does it pay?" cites nothing, "who is eligible for the Adarsh Gram
  component?" cites `Guidelines.pdf`, and the Tamil equivalent answers in Tamil
  from the same English source.
- **Retrieval failing cannot take the assistant with it.** A corpus that will
  not load is a missing enhancement; the listing path still answers what it can.
- **`is_ready()` counts nothing.** It runs on every unmatched question and only
  ever needed to know whether the corpus is empty, so it is an `exists` check.

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
