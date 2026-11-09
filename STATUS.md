# VoicePath — Build Status

> **This file is the live todo list.** It is updated every time a task is completed.
> Start at **To-do** — that is the working checklist. **Next up** carries the
> detail behind the top items; everything below it is the record of the build.
> Last updated: 2026-11-05 (tests on every push; skills people described now reach the taxonomy)

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

- [x] **`/health` does not notice a schema it cannot use.** Fixed 2026-11-09:
      it checks every table and column a migration added (`db.REQUIRED_SCHEMA`),
      lists `database` as degraded and names the migration to apply under
      `database.schema`; startup logs it. A test reads every file in `db/` and
      fails if a migration adds something the list does not name.

### Now — correctness, and the largest spec gaps

- [ ] **Most of the original twenty PDFs still have no URL.** Checked
      2026-11-04; only a link whose file is byte-identical to ours was
      recorded, and the API fills it in on its next start:
      `NULM-SUH-Guidelines.pdf` → nulm.gov.in. Three more are very likely
      right but their sites refused this environment, so confirm them by
      opening each and comparing before pasting into `sources.json`:
      `NLMGuidelinesJan2025.pdf` → dahd.gov.in/sites/default/files/2026-04/NLMGuidelinesJan2025.pdf
      (same file name); `PM_SETU_ITI_Upgradation_Guidelines.pdf` →
      dgt.gov.in/sites/default/files/2025-10/PM-SETU-Guidelines-Component-I-Upgradation-of-ITIs.pdf
      (same title, 2.64 MB); `PMGSY_RCPLWE_Road_Connectivity_Guidelines_2017.pdf`
      → pmgsy.nic.in/sites/default/files/RCPLWEA22feb17.pdf. PM-AJAY's
      `Guidelines.pdf` (May 2023) is listed on socialjustice.gov.in/schemes/104.
- [x] **Nine of the twenty PDFs were not government documents** — replaced
      2026-11-04. Each `*_Detailed_Scheme_Information.pdf` /
      `*_Information_Summary.pdf` was generated with ReportLab (several said
      so: "a prepared informational summary, not an official Government
      notification") yet was cited like one. All nine are rejected in the
      corpus and deleted from the repo; eleven official PIB releases (Dec 2024
      to Jul 2026) replace eight of them -- Fund of Funds 1.0 and 2.0, KVIC
      and Gramodyog Vikas Yojana, NMDFC credit and marketing, National SC-ST
      Hub, PMMSY (for the fishermen summary), MGNREGA with Project UNNATI,
      SFURTI, SMAM -- and `scheme_names.py` points each scheme at its own.
- [ ] **No official text found for the SCDC scheme** (Scheme of Assistance
      to State Scheduled Castes Development Corporations). Its summary was
      rejected with nothing in its place, so the assistant now says it does
      not have that rather than quoting a summary. Add a release when one is
      found.
- [x] **Listings 18–20 deactivated** 2026-11-04 (test entries, confirmed).

- [x] **Experience cannot be corrected, only seen** — fixed 2026-11-04.
      *Not right? Change it* beside the number on `/understanding`; see *Done
      on 2026-11-04 — experience can be corrected*.
- [x] **`/health` looked healthy while Groq's allowance was spent** — fixed
      2026-11-04: it now reports the model as degraded, says why and until
      when, and the screens say so. See *Fixed on 2026-11-04 — /health said
      the model was fine while it refused every call*.
- [ ] **The daily allowance itself is still the ceiling.** Being honest about
      running out is not the same as not running out: a larger Groq tier, or a
      second provider to fall over to, is the answer to that.

- [x] **Two live schemes had no required skills** — fixed 2026-09-12.
      `Pharma Business` now requires Retail Sales, `Plumbing Works` requires
      Plumbing. Every active scheme declares at least one skill.
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
- [x] **Filters on the scheme list** (§17): kind, where and skill done 2026-11-05
      (see below). Experience is not a filter: the ranking already weighs it.
      `services/schemes.py` already filters by district, so the query shape
      exists; mostly `app/schemes/page.tsx` plus query parameters on the list
      route. Do it after Jobs/Training — the type filter is most of the point.
- [x] **Place names render in English inside non-English sentences.** Fixed
      2026-11-05: listings carry `location_names` from the gazetteer, and the
      explanations -- template and model -- use the reader's script.
- [x] **An error already on screen does not follow a language switch.** Fixed
      2026-11-09, along with the API's English messages: every error response
      carries a `code` (`backend/app/errors.py`), the frontend says each code in
      English, Tamil and Hindi (`errorCodes` in `lib/i18n.ts`), and screens keep
      the cause (`lib/problems.ts`) rather than a sentence, so it is put into
      words in the language being read -- checked switching ta → hi → en with
      an error on screen. `tests/test_error_codes.py` fails if a code lacks a
      translation or a mapped message disappears.
- [x] **`npm run lint` does not exist** — fixed 2026-11-03 by dropping the
      script. `npm run typecheck` is the check that exists. Adding eslint
      properly is still open if anyone wants it; it would arrive with its own
      backlog of findings.
- [ ] **The motion layer has not been seen in a browser.** It compiles, `/`
      still prerenders, and every rule degrades under `prefers-reduced-motion`
      — but no screenshot was taken, because this environment has no browser.
      Worth one look on a real phone before it is shown to anyone.

### Embeddings — credits being added

- [ ] **The Hugging Face Inference API is out of credits** (402 Payment
      Required since at least 2026-11-04 15:39 UTC). Decided 2026-11-04: the
      owner adds HF credits. Until then a skill is accepted only when said by
      name or alias -- one described in other words is shortlisted by its
      words for the model or the person to confirm (2026-11-05) -- the
      assistant searches documents by keyword only, and the 27 new skills
      (24 + 3 from `db/011`) and 24 new official documents cannot be embedded.
      Engine Diagnostics' embedding was also cleared by `db/011`, because its
      aliases changed.
      After adding credits nothing else is needed: since 2026-11-09 the
      catch-up retries every half hour while anything is missing, and
      `/health` shows the backlog under `catch_up`. `/health` shows
      `"embeddings": {"status": "payment_required"}`. Options: buy HF
      pre-paid credits or PRO; or move to a provider that serves the same
      `multilingual-e5-base` model, so stored vectors stay valid. A different
      model means re-embedding the taxonomy and re-ingesting every document.
      The startup catch-up finishes the embedding on its own once it answers.

### Safety

- [x] **A plea for help was answered with a privacy notice** — fixed
      2026-11-04. See *Fixed on 2026-11-04 — a plea for help got a privacy
      notice*.
- [x] **The distress patterns are a fixed list.** Strengthened 2026-11-09: the
      list gained threats, attacks, feeling unsafe, self-harm, being held and
      bonded labour in all three languages (each with its nearest everyday
      sentence as a negative test), and "save" now counts only as a cry --
      "I need work to save my family" no longer triggers it. A second net:
      the intent classifier (every transcript and typed line) and the
      assistant (every question) also return `someone_in_danger`, at no
      extra request, and either one saying so shows the helplines.
      `tests/test_safety_net.py`. Keep adding phrasings from the question log.

### Scheme Q&A (RAG) — after the 2026-11-04 fixes

- [ ] **Review web pages at `/admin/sources`.** Pages the assistant finds by
      web search now wait there as *Waiting for review* and say nothing until
      approved. Approve only pages that describe a scheme's rules, benefits or
      how to apply.
- [ ] **Groq's daily allowance still bounds the assistant.** When it runs out,
      a question that names a covered scheme is answered by quoting that
      scheme's own passage; anything else is refused until it resets.
- [ ] **Scheme names live in `backend/app/data/scheme_names.py`.** Add a
      document's scheme names there when you ingest it, or questions that
      name it are searched across everything instead of its own text.

### After the 2026-11-03 outage

- [x] **A page opened during an outage said "cannot reach the server" until
      reloaded** — fixed 2026-11-03. The health check gave up after ~45 s and
      never asked again, so pages opened while the backend was down stayed
      broken after it recovered. It now keeps asking every 15 s (and at once
      when the tab is looked at again or the network returns) and recovers by
      itself. The message no longer tells a beneficiary to "start the backend".

- [x] **Confirm the keep-alive runs** — its first scheduled run, 2026-11-04,
      passed. Actions → *Keep the backend and
      database awake* → *Run workflow* once by hand. It should go green and
      print `"connected": true`. Supabase's exact definition of "inactive" is
      theirs; if the project pauses anyway, the job goes red and emails you.
- [x] **The API does not reconnect on its own.** Fixed 2026-11-05: it
      retries in the background and switches once nobody is mid-flow on the
      in-memory store (see *Done on 2026-11-05*). Only a database lost
      *after* startup still relies on asyncpg's pool, which replaces broken
      connections on its own once the database answers again.

### Near you (the map) — follow-ups

- [x] **Overpass from the deployed backend** — checked 2026-11-03, and it
      failed: `overpass-api.de` refused connections from Render and the mail.ru
      mirror timed out. Fixed by bundling a snapshot; see *Done on 2026-11-03 —
      the offices ship with the app*. Live lookups remain for searches the
      snapshot does not cover, and will fail the same way while those servers
      do.
- [x] **Create the first offices snapshot** — done 2026-11-04, after two
      Overpass-based runs failed (Python 3.11.9 missing on Ubuntu 26.04; then
      150 minutes of timeouts and 504s from both Overpass servers on GitHub's
      network). The workflow now builds it from Geofabrik's southern-India
      extract filtered with osmium, in about eight minutes: 1,291 offices
      around all 22 towns, OpenStreetMap data as of 2026-11-03 -- e.g. Salem
      has the Government ITI and polytechnics, the Collectorate, the RTO and
      30 bank branches. One police training college was caught on review and
      is now excluded by `categorize`. OpenStreetMap has no employment
      offices mapped near most towns, so that category is mostly empty.
- [ ] **Openings are pinned at their town's centre.** The catalogue records a
      town, never an address, so that is all the map can honestly show — and it
      says so. Real coordinates need `latitude`/`longitude` on `schemes` (a
      migration — mind the deploy order above) and a field in the admin form.
- [x] **OpenStreetMap's own tile server is for light use** — resolved
      2026-11-04: the map now uses OpenFreeMap, which is built for free public
      use with no limits. OSM's server is only the fallback if it is down.
- [x] **The gazetteer is 22 towns around Salem and Erode.** 49 since
      2026-11-05: a town in every one of Tamil Nadu's 38 districts (see
      *Done on 2026-11-05*). Adjacency between the new districts is not
      recorded, so a neighbouring district there scores as "different
      district" -- conservative, not wrong.

### Later — scale, breadth and loose ends

- [x] **NER is built but unused.** Deleted 2026-11-09: nothing called it, and it
      put `ner` in every production health report's degraded list.
- [x] **Audio retention is three-quarters wired.** Decided 2026-11-05: make it
      honest. Nothing ever kept a clip, so the toggle that promised it is gone
      (see *Done on 2026-11-05*).
- [x] **Only 16 schemes, seeded** — 11 national schemes added 2026-11-04, each
      quoted from its official release; see *Done on 2026-11-04 — national
      schemes, more skills, official documents*. District openings are still
      the 16 seeded ones: data.gov.in publishes district catalogues under
      GODL-India, and the schema plus admin importer already fit.
- [ ] **National scheme figures date.** Each scheme quotes a dated release
      (its `source_reference` ends in the date). When a ministry announces new
      amounts or extends a scheme, fetch the new release, replace the file in
      `backend/data/scheme_docs`, update the quote in `catalogue.py`, and
      regenerate `db/010`. `tests/test_national_schemes.py` fails if a quote
      and its release disagree.
- [ ] **Stand-Up India was left out** on purpose: its last official extension
      ran to 2025 and no release confirms it is open now. Add it when one does.
- [x] **Listings 18–20 were test entries** ("Pharma Business / REC",
      "Plumbing Works", "Carpentry / BlockChain Innovation Club", with
      github.com, vercel.com and rajalakshmi.org as "official" links) —
      deactivated 2026-11-04, not deleted.
- [ ] **Retrieval still cannot reach matching.**
      `tests/test_assistant_routing.py` asserts the separation by reading
      `matching.py`'s source rather than its imports, which is weaker than it
      looks. Tighten the assertion.
- [x] **Rate limiting is per-process.** Fixed 2026-11-05: the counters live in
      a shared Render Key Value store (see *Done on 2026-11-05*).
- [x] **Confirm `TAVILY_API_KEY` is set in the deployed environment.** Confirmed
      2026-11-09: production `/health` reports `"search": "tavily"`. Without
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
| 5. Backend tests | ✅ Done — **719 passing**, 7 skipped |
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
  009_document_source_url.sql
                             a document's URL through retrieval, and the
                             verification gate actually enforced
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
  tests/                     332, fully offline -- no keys, network or database.
                             325 pass; 7 skip without one (intent topic check)
  data/scheme_docs/          Source PDFs, committed (~28MB): 20 central and
                             state scheme documents -- PM-AJAY, PMAGY, PM SETU,
                             PMGSY, NHDP (handicrafts and handloom), NLM, NULM,
                             SFURTI, Khadi, the startup playbook and more.
                             Public documents, kept so retrieval is
                             reproducible. Every filename says what it holds:
                             a citation shows the source file, so a hash for a
                             name is shown to the person reading the answer

frontend/
  app/
    page.tsx                 Landing
    speak/                   Mic, live waveform off real amplitude
    understanding/           Editable skill cards, each showing its evidence
                             and now its confidence against the threshold
    understanding/disambiguate/   Low-confidence screen
    schemes/           Ranked feed
    schemes/[id]/      RSC detail + score bars with their weights
    about/                   What this is, what it will not do
    passport/                Skill Passport (prints; recordings are never kept)
    admin/                   Schemes, taxonomy, sessions (no transcripts)
  components/                SkillCard, Waveform, MatchRing, AskVoicePath,
                             PageBackdrop, FlowRail/FlowBar, AdminOverview, ...
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

### Phase 5 — Backend tests ✅ (894 passing, 7 skipped)
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
- [x] `test_chunk_quality.py` — card-layout prose survives; contents pages and score tables do not
- [x] `test_scheme_qa_refusal.py` — a failed model refuses instead of asserting a passage
- [x] `test_typed_skill.py` — normalize tolerates an entry it has never stored
- [x] `test_typed_input_validation.py` — off-topic text never becomes a skill; a question is still answered
- [x] `test_years_parsing.py` — "two-wheelers for six years" is six, and "two bikes" is nothing

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
- [x] `/passport` — Skill Passport (the audio toggle was removed 2026-11-05)
- [x] `/schemes` — ranked feed, reasons weighted equal to titles
- [x] `/schemes/[id]` — RSC detail + score bars + Ask VoicePath

### Phase 8 — Admin ✅
- [x] `/admin/schemes`, `/admin/taxonomy`, `/admin/sessions` (read-only, no transcripts)

### Phase 9 — Verification ✅
- [x] `pytest` — 325 passed, 7 skipped (the 7 need a database)
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
- **Rate limiting is per-process.** Multiplies behind multiple instances; move
  the counter to Redis before scaling.

---

## Fixed on 2026-11-04 — /health said the model was fine while it refused every call

On 2026-09-12 Groq's daily allowance ran out. Every extraction, explanation
and answer fell back to its rule-based path -- named skills only, template
explanations, quoted passages -- and `/health` went on reporting `llm: groq`
with nothing degraded, because it reported what was *configured*. Nobody using
the site was told why the answers had become thinner.

**Now** `services/llm.py` remembers the last real outage: a rate limit, a spent
daily allowance, a rejected key, a model Groq has retired, a server error, no
connection. It holds for as long as Groq's `retry-after` says (or the "try
again in 7m12s" in its message), five minutes when it says nothing, a day at
most, and the next successful answer clears it at once. A 400 is about one
request, not the service, and is not recorded. While it holds, `/health` lists
`llm` as degraded and adds `"llm": {"status": "daily_limit", "since": …,
"until": …}`; it is `{"status": "ok"}` when answering and `"offline"` when no
model is configured, so the two kinds of degraded are told apart.

**On screen**: a notice in the person's language -- the language service is
not answering, busy or out of today's allowance; until it is back only named
skills are read and answers are simpler -- with "back around 3:04" when the
provider gave a time. It appears on `/understanding`, `/schemes` and, new, the
scheme page where the assistant is. The frontend now re-reads `/health` every
60 seconds while the tab is in view (and on returning to it), so a page opened
before the limit was hit picks it up within a minute; a tab in the background
does not poll, so it does not keep a free-tier server awake.

`tests/test_llm_status.py`, 17 tests, against a mock Groq. Checked in a
browser against a fake Groq answering 429 with a ten-minute `retry-after`:
`/health` flipped to `daily_limit` with the right `until`, and the Tamil notice
appeared on the open scheme page at the next refresh.

**Also fixed on the way**: the scheme page was 458px wide on a 390px phone --
the title, description and assistant all ran off the right edge -- because
below the `lg` breakpoint its grid had no column template, and an implicit
column cannot shrink below its widest content. `grid-cols-1` fixes it.

---

## Done on 2026-11-05 — skills people described now reach the taxonomy

Of the first 66 skills people described in production, **12 matched nothing**:
five were an engine mechanic's ("engine engine-aa velai paarthen",
"identifying engine problems by sound", a Tamil sentence about knowing the
fault from the engine's sound), six from the medicine trade ("Pharmacist",
"pharmaceutical drug dealer" -- the licensed wholesale trade), one a football
question. And while the embedder is out of credits, *every* skill not said by
its exact name or alias landed nowhere.

- **Three skills** (`db/011_more_skills.sql`, applied to production and
  checked value by value against the catalogue): Engine Repair and Overhaul
  (SK016), Pharmacy and Chemist Shop Work (SK118), Medicine Sales and
  Distribution (SK096), with Tamil and Hindi names and aliases, linked at 0.40
  to the eight schemes open to any trade. Engine Diagnostics gained the
  phrases people used as aliases. Bare "drug dealer" is deliberately not an
  alias and shortlists nothing.
- **A keyword shortlist** (`taxonomy.keyword_candidates`) for when the
  embedding search offers nothing or is down: skills sharing a *rare* word
  with what was said ("engine", "pharma", "சத்தம்"), with word forms folded
  ("diagnosing" / "diagnostics", Tamil case endings). It only offers -- the
  model chooses among it, constrained to it, or the person does; shared
  words never accept a skill alone. Generic words ("work", "problem",
  "years", "வேலை", "काम") shortlist nothing.
- **Tests**: `tests/test_skill_shortlist.py` (28) -- every production phrase
  reaches its skill with the embedder down; the shortlist never accepts; the
  model cannot choose outside it.
- **The passport prints** (`app/passport/page.tsx`, `globals.css`): a "Print
  or save as PDF" button, with a hint that "Save as PDF" keeps a copy on a
  phone. On paper the site's menus, the audio toggle and the buttons are
  hidden, the green header becomes black on white (browsers drop background
  colours, so it used to print blank), and a footer says when it was
  recorded and that it is the person's own words, not a certificate. Checked
  in Chromium's print rendering in English and Tamil.
- **Filters on the scheme list** (`components/SchemeFilters.tsx`): kind (jobs;
  training and apprenticeships; own work and loans), where (in a town, or
  open anywhere in India) and, once matched, which of the person's skills a
  result is for. One choice per group, each with the count it would leave;
  options with nothing behind them, and groups with no real choice, are not
  shown; an emptied list says so and offers "Show everything". Filtering only
  hides rows -- the ranking and reasons stay the server's. It narrows the
  eight results `/api/schemes/match` returns (each costs a Groq explanation,
  so the page does not ask for more), and the whole catalogue when browsing
  without a session. Checked in Chromium.
- **Town names in the reader's script** (`services/places.py`,
  `explanation.py`, `lib/i18n.ts`). Listings carry `location_names` -- the
  gazetteer's names, the ones the map already labels towns with, never a
  spelling made up on the spot -- and scheme rows, the scheme page and the
  explanations use them; the model is given the town in the language it
  writes. The Tamil sentences were rephrased ("இடம்: சேலம் — …") so a name
  needs no case ending glued on; "சேலம்லேயே" would have been wrong. A place
  the gazetteer does not know keeps its catalogue spelling. Tests:
  `tests/test_place_names.py` (11).
- **The API reconnects after a database outage** (`services/db.py`,
  `main.py`, `repository.py`). Decided 2026-11-05: wait until nobody is
  mid-flow. A database that did not answer at startup is retried after 15s,
  30s, 1m, 2m, then every 5 minutes. Once it answers, the switch waits until
  no in-memory session has been used for 30 minutes -- an outage session
  carries the in-memory catalogue's skill and scheme ids, which are not the
  database's, so continuing it against the database would match the wrong
  rows. Then the pool opens, the in-memory sessions are retired, the
  taxonomy and scheme caches are rebuilt from the database, and the corpus
  catch-up runs. A request for a retired session gets **410** and "This
  session was started while VoicePath's database was down, so it was not
  saved. Please start again from the beginning." `/health` shows
  `"reconnect": "retrying"` or "waiting for sessions started during the
  outage to finish" meanwhile. Tests: `tests/test_database_reconnect.py` (12).
- **A town in every district** (`app/data/places.py`, `matching.py`). The 27
  district headquarters the map lacked, so the gazetteer covers all 38 Tamil
  Nadu districts with 49 towns. Coordinates and Tamil and Hindi names are
  OpenStreetMap's, looked up through Nominatim (Geofabrik and Overpass are
  unreachable from the build container); Wikidata fills what OSM lacks --
  eight Hindi names (Ramanathapuram's OSM one is corrupted, the word doubled)
  and Pudukkottai's and Viluppuram's coordinates, where Nominatim found no
  town object. Each entry names its source object. The matcher learns each
  town's English variants (Tanjore, Tuticorin, Ooty, Nilgiris, Chingleput,
  Villupuram…), Tamil stems that absorb case endings, and Hindi names; a test
  forbids any alias being a prefix of another town's. The offices snapshot
  lists the new towns as not yet fetched until the monthly refresh (run by
  hand on 2026-11-05) fills them. Tests: `tests/test_more_towns.py` (44).
- **Voice recordings: the passport tells the truth.** Decided 2026-11-05.
  No code path ever kept a recording, yet the passport offered "Keep my voice
  clips so employers can hear me say it" and stored the answer -- a promise
  nothing kept, and nothing for a retention clean-up to delete. The toggle,
  its endpoint (`POST /api/sessions/{id}/audio-retention`), its session state
  and copy, the `ALLOW_AUDIO_RETENTION` switch and the assistant's "you turned
  on keeping clips" answer are gone. The passport now says, in all three
  languages, that the recording was used only to write down what was said and
  is not kept. `db/012_no_voice_clips.sql` (applied) cleared the two sessions
  that had the flag set; there were no clip links. The API now runs
  `purge_expired_audio` daily -- before, nothing called it. Tests:
  `tests/test_audio_purge.py` (4), and `tests/test_api.py` holds that nothing
  can turn keeping on.
- **Both known security limits fixed** (decided 2026-11-05):
  - **Rate limits are shared across instances.** The counters, and the
    admin-token lockout, live in a free Render Key Value instance
    (`voicepath-ratelimit`, Singapore, beside the API; reachable only from
    Render services in that region) via `RATE_LIMIT_REDIS_URL`. One pipelined
    round trip per request; keys hashed and self-expiring. If the store stops
    answering, counting falls back to the process for 30 seconds at a time --
    nobody is refused for want of a counter -- and `/health` shows
    `rate_limits.store`. Tested against a real Redis server, which the test
    workflow installs (`tests/test_shared_ratelimit.py`, 9).
  - **A session opens only with its secret key.** 256 bits, given once at
    creation, sent back only in `X-VoicePath-Session-Key`, stored only as its
    SHA-256 (`db/013_session_keys.sql`, applied before the code). Checked in
    every per-session repository function; a missing or wrong key reads as
    "not found"; sessions from before are asked to start again. The frontend
    keeps the key in `lib/api.ts` (and sessionStorage, for reloads) the moment
    the session exists. Checked end to end in Chromium: the flow works with
    the key, every session request carries it, it is never in a URL, and
    without it nothing opens (`tests/test_session_keys.py`, 11).
- **A voice download can no longer hang a deploy** (`scripts/fetch_voices.py`).
  On 2026-11-05 a Render build hung for over fifteen minutes on a voice
  trickling in from Hugging Face -- the only timeout fired after ten minutes of
  total silence -- and the session-keys deploy queued behind it. Now: five
  minutes per file at most, 60 seconds of silence ends an attempt, three
  attempts, written under a temporary name until complete. A voice that still
  will not come fails the build, which leaves the running version live.
  Tests: `tests/test_fetch_voices.py` (2).
- **UI pass** (decided 2026-11-05: all four of readability, phone layout,
  plain-language skill cards, polish), from screenshots of every screen on a
  phone and a desktop:
  - *Readability.* The three faintest text greys measured 2.4, 2.9 and 4.0:1
    against the paper -- under the 4.5:1 small text needs. Raised to 4.7-6:1
    in the tokens, so every use moved. Text floor of 12px (it went to 10px).
    On touch screens the small buttons and chips are at least 40px tall.
    Focus rings one step darker.
  - *Phone layout.* The step bar names only the current step there, with
    "Step 2 of 5" (the labels used to be cut off mid-word); the Speak
    screen's spacing shrinks so the mic button is on screen and the
    instruction is readable size, said once rather than twice; Admin moved
    from the main menu to a new footer.
  - *Skill cards* say "Matched", "Please check this one" or "Kept in your
    words", with the kind of work; the code, the score and the threshold
    are one tap away under Details. The passport shows the kind of work,
    not the code.
  - *Polish.* Placeholders shaped like the results while they load; an
    empty result list offers "Add more about your work" and "See what is
    near you"; the next step is an open accent ring in the step bar; dark
    mode follows the device (screen only -- print stays black on white),
    with a lighter accent so text on it stays readable.
  Checked in Chromium, light and dark, phone and desktop; no page scrolls
  sideways.
- **Tests on every push** (`.github/workflows/tests.yml`): pytest, the
  frontend type-check and a production build, on every push to `main` and
  every pull request. Until now nothing checked a push before it deployed.

## Done on 2026-11-04 — security review and hardening

Asked for: "implement cyber security to all the points and secure the website
more". A review of the backend, frontend, database, deploys and dependencies
found these, all fixed; `SECURITY.md` describes what is now in place.

- **Critical: Next.js 16.3.4** was inside a critical advisory (remote code
  execution via image optimisation, among nine) -- now 16.4.5; `sharp` and
  `source-map-js` updated with it. **Starlette 0.41.3** carried eight
  advisories -- now FastAPI 0.162 on Starlette 1.10; python-multipart 0.0.33;
  pytest 9.2. `npm audit` and `pip-audit` both report nothing.
- **Rate limits could be reset at will**: they were keyed on a header the
  client chooses. Now per session, per address and per route for everyone, all
  enforced.
- **Server-side request forgery**: pages from search results were fetched
  with any redirect followed, so a result could reach internal addresses.
  Now public addresses only, every hop checked, 2 MB cap.
- **Memory exhaustion**: request bodies and audio uploads were read whole
  before any size check. Now capped as they stream in; uploads must be audio;
  text fields have length limits.
- **No security headers** on the site or the API. Now CSP (static policy,
  checked page by page in a browser with zero violations, map included), HSTS,
  frame denial, nosniff, referrer and permissions policies; `no-store` on API
  responses; `X-Powered-By` removed.
- **Admin tokens could be guessed endlessly**: now locked out after ten wrong
  tokens per address (or a hundred overall) per 15 minutes, and a startup
  warning for a short bootstrap token.
- **API docs public in production**: off on Render and in production.
- **CORS admitted any header**: now only the three the frontend sends.
- **GitHub Actions** now pinned to commit SHAs (v6 releases, which also ends
  the Node 20 deprecation warnings), plus a weekly read-only
  `security-audit.yml`.

Checked and fine as they were: no secrets in git history, no HTML rendered
from data, every external link `noopener`, admin tokens stored hashed and
compared in constant time, row-level security on every table. Left as is:
Supabase's warning about pgvector in the `public` schema.

`tests/test_security.py`, 31 tests: each finding's attack run against its fix.

---

## Fixed on 2026-11-04 — the embedder ran out of credits and every skill was a 500

Found while checking the national-schemes deploy: the Hugging Face Inference
API answered **402 Payment Required** ("Purchase pre-paid credits to continue
using Inference Providers"). Normalization embeds every skill a person
describes, nothing caught the error, and `/api/profile/extract` returned 500
-- the main flow, from describing your work to seeing a result, was down.
`/health` still said `embeddings: hf_api`.

Now the outage costs recall, not the request:

- **Normalization** falls back to exact names and aliases (in all three
  languages). "Welding" still becomes Welding; "I join metal pipes with heat"
  stays an unplaced skill with its evidence, as any unplaceable skill does.
- **Matching** runs without fresh vectors; an unplaced skill earns nothing,
  which is what it earns anyway.
- **Document search** falls back to keyword search alone.
- **`/health`** lists `embeddings` as degraded with the reason
  (`payment_required`, `rate_limited`, `unreachable`...), the way it now does
  for Groq, and the screens show the "reading only what you name" notice.

`tests/test_embedding_outage.py`, 7 tests. Restoring full recall needs the
decision in the to-do above.

---

## Done on 2026-11-04 — national schemes, more skills, official documents

Asked for: more schemes and openings, official links, more skills, more scheme
documents -- real sources only, national schemes.

**Eleven national schemes**, each open across India: PM Vishwakarma, PMKVY
4.0, PM-NAPS, Jan Shikshan Sansthan, DDU-GKY, RSETIs, PMEGP, PM SVANidhi,
PMMY (Mudra), NAMASTE and PM-DAKSH. Every description is sentences copied
exactly from the most recent official release found -- PIB and ministry
releases from 2023 to July 2026 -- because the explanation layer may ground
itself only in that text. `tests/test_national_schemes.py` checks all 44
sentences against copies of the releases. Each scheme's link is the release
quoted, or the portal that release names (Skill India Digital Hub for PMKVY,
the PM Vishwakarma portal). No monthly pay is recorded for any of them: a
₹500-a-day stipend or a loan is not a wage. Stand-Up India was left out
because no release confirms it runs past 2025.

Most scheme sites (pmkvyofficial.org, kviconline.gov.in, standupmitra.in...)
were unreachable from the build environment, and myScheme serves its content
only to its own scripts; PIB's releases were reachable and are the
government's own publication, so they are the source throughout.

**Matching had to learn two things** (`services/matching.py`):

- *One trade is enough* (`schemes.skill_match = 'any'`). PM Vishwakarma covers
  eighteen trades; scored as coverage of all of them a tailor earned 1/18 and
  never saw it. Now the best single trade counts, weighted by how squarely
  the scheme names it: 1.0 for a trade its release names, 0.4 for "open to
  any trade" (PMKVY, Mudra). Only named trades are claimed in an explanation;
  the rest say "open to many trades, not one in particular".
- *Open everywhere.* "All India" scores as the person's own district (0.85).

And one guard, found by testing: the first version let seven generic schemes
tie at 0.785 for everyone and push a welder's own local job off the first
page. Generic schemes now score below a partial match in the person's own
trade (0.685 against 0.74), and at most three appear in a result list; all of
them are on `/nearby` under *Open anywhere in India*.

**24 more skills** (68 in all), with Tamil and Hindi names and the words
people use: PM Vishwakarma's trades not already present (a new *Traditional
Crafts* category -- boat making, blacksmithing, goldsmithing, pottery,
cobbling, garland making, fishing nets...), barbering, laundry, sanitation
work, waste collection, domestic work, street vending, handloom, solar
installation, fishing, food processing.

**13 official documents** for the assistant, in `backend/data/scheme_docs` as
text with each release's address in `sources.json`, and scheme names for each
in `scheme_names.py` so a question naming PMEGP searches PMEGP's own text.

**The API now catches up on startup** (`services/corpus_sync.py`): it embeds
skills that have no vector, ingests bundled text documents not yet in the
corpus, and fills document URLs newly recorded in `sources.json` -- only what
is missing, never re-opening a rejected document or overwriting a URL, and
nothing at all if embeddings are offline. Before this, each of those needed a
script run by hand against production with its password.

Applied to production with `db/010_national_schemes.sql`; every scheme and
skill row was checked against the catalogue by checksum afterwards.

---

## Done on 2026-11-04 — experience can be corrected

Years of work are a quarter of every match score, and a misheard number --
Whisper reading "six" as "two" -- could be seen on `/understanding` but fixed
only by recording everything again.

**Now** the number has *Not right? Change it* beside it (*Add it* when none
was heard). It opens a number field in place, in the screen's language;
half years are allowed, and anything outside 0-70 is refused with a message in
that language rather than the browser's own. Saving calls
`PUT /api/profile/experience`, which changes that one field -- skills, their
evidence and the rest of the profile stay exactly as extracted -- and, if the
number actually changed, **deletes the stored matches**, because every one of
them was scored on the old number. The browser drops its copy too, so the
next visit to `/schemes` ranks again, and a scheme page opened in between
shows no stale score. Saving the same number keeps the ranking.

It is the person's own statement, so unlike an extracted skill it needs no
quote from the transcript: the rule that extraction may not invent binds the
model, not them. `tests/test_experience_correction.py`, 12 tests, including
that a scheme asking for experience scores lower after six years is corrected
to half a year. Checked in a browser in Tamil: edit, save, the new number on
screen, and `/schemes` calling match again.

---

## Fixed on 2026-11-04 — a plea for help got a privacy notice

The production question log held "என் பக்கத்தில் ஒரு படிக்கு தெரியாத பெண்ணு
இருக்கு, பிள்ளீஸ் காப்பாற்றுங்கள்" -- there is an illiterate woman next to me,
please save her -- asked three times. Each time the assistant explained that
their voice had not been recorded.

**Now**, a question, a typed line or a spoken transcript that says someone is
in danger, being hurt or thinking of ending their life is answered with
**112** first (free from any phone, day and night, in any of the three
languages), then **181** (women), **1098** (children) and **14416**
(Tele-MANAS, mental health), and the plain statement that VoicePath cannot
send help itself. On screen the numbers are tap-to-call links, in a panel that
replaces the answer rather than sitting beside it: at the top of
`/understanding`, and in the assistant on a scheme page.

**Deterministic, not the model's call** (`backend/app/services/safety.py`):
fixed patterns in English, Tamil and Hindi, checked before retrieval, before
the LLM and before every listing rule, so it answers when Groq is rate-limited
or down. The assistant's prompt carries the same instruction for phrasing the
patterns miss.

**Tuned against the people it serves**, whose work descriptions use the same
words. Tested as *not* matching: "குடும்பத்தை காப்பாற்ற வேலை வேண்டும்" (I need a
job to support my family -- only the pleading form of காப்பாற்று counts),
"பெயிண்ட் அடிக்கிறேன்" (I paint) and "டைப் அடிப்பேன்" (I type) -- beating counts
only with a person as its object -- "my job is in danger", "can you help me
find a job?", "क्या मदद मिलेगी?". A false alarm costs one helpline message; a
miss costs more, so borderline forms lean towards matching.

**Where it is wired**: `/api/assistant/query` returns `urgent: true` and the
helpline answer; `/api/query/understand` flags `urgent` whatever the
classifier says, and the understanding screen then asks the assistant with
the whole transcript; `/api/profile/skills` checks before extraction, so "my
boss beats me, I am a welder" does not come back as one welding skill and
nothing else. Nothing is dialled, reported or stored beyond the question log
that already existed. `tests/test_safety.py`, 51 tests; checked in a browser
on all three paths.

---

## Done on 2026-11-04 — a current-looking map, labelled in the reader's language

"The map is not the current map." The data was current -- OpenStreetMap's own
tiles are rendered from live data -- but the standard style looks like a map
from another decade, and it can only label a place in whatever language its
local `name` tag happens to be.

The Near you map now draws OpenFreeMap's **Liberty** vector style with
**MapLibre GL 6.15** (Leaflet removed): current OpenStreetMap data, free, no
key, no usage limits, sharp at every zoom. Chosen from four styles rendered
side by side over central Salem; CARTO's Voyager was ruled out because it now
needs an API key.

**Labels follow the interface language** -- `name:ta` on a Tamil page,
`name:hi` on a Hindi one, the local name where there is no translation. Most
places around Salem have Tamil names in OpenStreetMap; few have Hindi ones, so
a Hindi map is mostly English. **The version matters**: MapLibre 4 drew Tamil
without reordering its vowel signs, so சேலம் rendered as சலேம் and கோட்டை
was scrambled. 6.15 includes the fix for Brahmic scripts and was checked in a
browser: சேலம், ஓமலூர், அயோத்தியாப்பட்டினம், இளம்பிள்ளை all render correctly.

**Kept from before**: one pin per town, office dots by kind, popups built with
`textContent`, the dashed search circle (now drawn by MapLibre, in the accent
token converted through a canvas because MapLibre cannot parse `oklch()`), no
"you" dot unless the device gave a location, list picks pan and open a popup,
popups survive the offices arriving late.

**Two bugs caught in testing, both fixed**: a pin clicked on the map toggled
its popup twice (React's selection and MapLibre's own click), so it never
opened; and the search circle waited on `isStyleLoaded()`, which stays false
while any tile is downloading, so it was never drawn.

**If OpenFreeMap is down** the map swaps once to plain OpenStreetMap tiles
rather than showing pins over nothing -- but only when the style itself fails,
not when a single tile times out. MapLibre's worker is copied into
`public/maplibre/` before every dev and build run (`scripts/copy-maplibre-worker.mjs`),
because inside a Next.js bundle MapLibre cannot find it on its own.

---

## Fixed on 2026-11-04 — the scheme Q&A cited football news

Found in the production question log (`assistant_queries`), not by a test:

| Asked | What it did |
|---|---|
| "kylian mbappe or lamine yamal" | Answered "from the scheme guidelines", citing match reports |
| PM-AJAY, misheard in Tamil | Answered about **e-Shram**, labelled as guidelines |
| "PM-KISAN" | "The passages do not mention PM-KISAN" — still labelled guidelines, with a citation |
| "பி.எ.ம்.ஸ்கி." | Raw scraped markup: `India image](https://…jpg) ![Empl…` |
| "sigaram thodu scheme" | "Not in the record" — with thirteen of its passages in the corpus |

**The corpus.** Web search had made every `.gov.in` page it fetched answerable
at once, and public broadcasters' news sites are `.gov.in`. 34 of 56 active
documents were fetched pages: match reports, exam syllabi, an election FAQ, an
SEO guide, a tea-plantation RTI, portal menus. Eighteen were set `rejected`
(reversible, and a re-fetch cannot revive them); PM Vishwakarma and the MSME
schemes page stay. The corpus is now 22 documents, 1,098 passages.

**Web search.** It now runs only when the model judges the question to be
about schemes; never fetches `excluded_domains` (news sites); and stores every
page `pending_verification`, Tier 1 included, for review on the new
`/admin/sources` page (with an excerpt of each page, and Approve / Reject).
Since a pending page cannot answer the question that triggered it, the search
runs in the background instead of keeping the person waiting through it.

**Grounding.** The model now returns `answerable` and `about_schemes` beside
its answer. An answer counts as grounded only if it is answerable *and* names
the passages it used — `used` alone let "the passages do not say" through with
a citation. The prompt also forbids describing one scheme's rules as
another's, and is told which local listing is on screen so "who can apply for
this?" is not answered from a central scheme.

**Named schemes.** `app/data/scheme_names.py` maps scheme names (English, Tamil,
Hindi) to their documents — the PM-AJAY guidelines are stored as "Guidelines".
A question that names one is searched in that scheme's documents only.
Measured why it matters: with a Sigaram Thodu question vector, unrelated PM-AJAY
passages still score 0.85, above the 0.74 usable floor. When Groq fails, a
question naming a scheme is answered by quoting that scheme's own passage, with
its citation; anything else is still refused.

**Routing.** Listing keywords (pay, distance, certificates…) matched as
substrings: "far" in "farmer", "pay" in "repayment", "data" in any document
question. They now match whole words, and decide the route only when a listing
is on screen and the question names no covered scheme.

**Keyword search.** It required every word of the question, stop words
included: four natural questions matched 0 passages each against the live
corpus. It now ORs the content words (14–247 candidates each) and lets the
rank fusion order them.

`tests/test_rag_fixes.py` has a test for each of these. Backend: 499 passed.

---

## Done on 2026-11-03 — the offices ship with the app

The live check after the outage fix found the map's "Places that can help"
empty in production. From Render, `overpass-api.de` refused connections and
the mail.ru mirror timed out; the page said so honestly, but the feature was
not there.

Offices around every town the map knows are now fetched ahead of time by
`app/scripts/fetch_support_places.py` and shipped as
`backend/app/data/support_places.json` (OpenStreetMap data, ODbL, attributed in
the file and on the page). A search is answered from it when its whole circle
sits inside a fetched town's 25 km circle — partial overlap is not coverage,
because the missing part could hold the nearest ITI. Everything else still asks
Overpass live. The same filters apply to both, and the page shows the
snapshot's date.

`PLACES_PROVIDER=offline` now means "no live lookups": the snapshot is local
data and still answers what it covers, the same way the bundled catalogue does.

The script asks for one kind of office around one town at a time, alternating
GET and POST with backoff — one query for all four kinds over 25 km timed out
on a busy server again and again, where four small ones got through. A town
counts as fetched only if all four kinds came back; one that did not is
recorded as such, and the API does not claim to cover it.

---

## Fixed on 2026-11-03 — a paused database took the whole API down

**What happened.** PR #8 merged and Render deployed it. The build succeeded;
startup did not. Every boot died connecting to Postgres:

```
asyncpg.exceptions.InternalServerError: (ENOTFOUND) tenant/user postgres.<project> not found
ERROR:    Application startup failed. Exiting.
```

The Supabase project had been paused for inactivity — the free tier does that
after about a week, and the last deploy was 2026-09-12. The pooler answers
"tenant not found" for a paused project. Render kept the previous deploy
nominally live, but the free instance sleeps when idle and every wake re-ran
the same startup, so the old version failed identically: the site was down
whichever code was deployed. Vercel built and served the frontend fine; it
had no backend to talk to. The new map code was not involved.

**Fixed, in four parts.**

1. **The project was restored** and checked before redeploying: 44 taxonomy
   rows, all embedded; 19 active schemes; 93 sessions; the 007 and 009
   columns present.
2. **The API starts without its database.** `db.init_pool` catches the
   failure, logs it in full, and falls back to the in-memory store — which
   every route already used when `DATABASE_URL` was unset. The catalogue,
   matching and the map need no database, so a database outage no longer
   takes them down too. It is not hidden: `/health` lists `database` as degraded
   with `"configured": true`, and the interface shows a notice in all three
   languages that a record may not be kept.
3. **The admin gate refuses during an outage.** The bootstrap token is
   honoured only while `admin_users` is empty, and with the database down
   nobody can see whether it is. Falling through would have treated "cannot
   check" as "empty" and reopened the backdoor for exactly as long as the
   database was down. It answers 503 instead.
4. **A keep-alive.** `.github/workflows/keep-alive.yml` calls `/health` every
   three days — it runs real queries — and fails loudly if the database is
   not connected.

Also: `/health` no longer publishes the raw driver error, which can name the
host, project or user. It gives the kind of error; the log has the detail.

`tests/test_database_outage.py` simulates the outage with a port nothing
listens on. Without the fix all ten of its tests fail exactly as Render did;
with it they pass.

---

## Done on 2026-11-03 — "Near you": the map

A new screen, `/nearby`, linked from the header, from `/schemes` and from every
scheme's own page (`/nearby?scheme=7` opens on that scheme's town). It shows
two things, kept visibly apart because they deserve different trust:

- **Openings** from the catalogue, grouped by town and ordered by straight-line
  distance. One green pin per town with a count — the record knows the town,
  not the street, and eleven stacked pins would each look like an address. The
  screen says they are marked at the town centre.
- **Places that can help** from OpenStreetMap via the Overpass API: training
  centres and ITIs, employment offices, government offices, banks. Each has a
  Directions link (a keyless Google Maps URL, which opens the Maps app on most
  phones) and a link to the OpenStreetMap record.

Stack (as first built): Leaflet 1.9.4 over OpenStreetMap tiles — replaced on
2026-11-04 by MapLibre GL and OpenFreeMap; see below. Free, no key, open data — the
same reasoning as the rest of the stack.

**Where the map centres**, in order of what is actually known: the device
location if the person presses *Use my location*; a town picked from the list;
the place they said while describing their work (through the matcher's own
`canonical_place`, so "சேலத்துல" and "सेलम में" both land on Salem); otherwise
"where the openings are", and the screen says it does not know where they are.
A "you" dot is drawn only for a device location — a spoken town is a town, not
a doorstep.

**Privacy.** A device location is rounded to two decimals (about 1.1 km) in the
browser before it is sent, rounded again on the server, sent in a POST body
rather than a query string (query strings land in access logs), held in
component state rather than session storage, and never written anywhere.
`tests/test_nearby.py` asserts the Overpass query never carries the precise
point.

**It does not rank.** Distance is information beside an opening; the audited
ranking stays on `/schemes`. `matching.py` does not import the places service,
and a test reads its imports to keep it that way.

**Overpass is volunteer-run, so the map does not wait on it.** Openings come
from `POST /api/places/nearby`, answered from the catalogue alone. Offices come
from `POST /api/places/support`, asked for afterwards. Endpoints in
`OVERPASS_URLS` are tried in order; a failure answers `unavailable` at once for
the next 60 seconds rather than making every request wait out the same
timeouts; success is cached for `PLACES_CACHE_HOURS`. "Nothing mapped here" and
"could not look" are different statuses and the screen says which.
`PLACES_PROVIDER=offline` turns the lookup off and `/health` reports `places`.

**What counts as help** was decided against a real Overpass response for
central Salem, now trimmed into `tests/fixtures/overpass_salem.json`. Colleges
count only by name (ITI, Industrial Training, Polytechnic, Skill, Handloom…),
so law, arts and medical colleges stay off a list about skilling. Police and
tax offices are excluded by tag and by name: most Salem tax offices carry no
`government=` tag, and some are named only in `name:en` — a filter reading
`name` alone let the GST offices through. The RTO stays, because a licence is
what the driving openings ask for.

Copy is written in Tamil, Hindi and English. Town names in the gazetteer carry
all three scripts, so on this screen at least a place renders in the reader's
script.

---

## Fixed on 2026-11-03 — the scheme page rebuilt itself on every load

**A hydration error on `/schemes/[id]`, in every language.** `AskVoicePath`
asked during render whether the browser can recognise speech. The server
cannot, so it rendered no mic button; the browser can, so it rendered one;
React threw the server HTML away (minified error #418) and rebuilt the screen
on the client. The check now runs after mount and both sides start without it.

**Spoken answers never played in development.** The same component's
`mounted` ref was set false by Strict Mode's mount → cleanup → mount, and
nothing set it back, so every answer looked like it arrived after the screen
had gone. The effect now sets it true on each mount.

**English on a Tamil page.** The facts under a scheme — "Pay", "Experience
asked for", "Certificates required", "2 years" — were literals, as was the
language switch's accessible name. All are in `lib/i18n.ts` now.

**`npm run lint`** pointed at `next lint`, removed in Next 16. Dropped.

**Backend lint.** Seven unused imports and one unused variable, found by
`ruff --select F`; removed. No behaviour change.

Found by driving every route in all three languages in a headless browser and
collecting console errors, then re-run after the fixes: 16 routes × 3
languages, no page errors.

---

## Fixed on 2026-09-12 — the stepper described a flow the app does not have

It listed *Speak → What I heard → What fits → Your passport*. The buttons go
somewhere else entirely:

```
/understanding  confirm  -> /passport
/passport       matches  -> /schemes
/schemes        open one -> /schemes/[id]
```

So the passport comes **before** the list, not after it. The stepper had the
last two the wrong way round, which is worse than having no stepper: it is a
confident wrong answer to *where am I*.

The order is now what the buttons actually do, and the journey that was always
there is written out in full:

**Speak → What I heard → Your passport → What fits → The one you pick**

The fifth step was folded into the fourth before. A scheme's own page is where
the whole journey was going, and it is not the same thing as the list it was
chosen from.

**It has no path of its own**, which the code now says plainly: a detail page
needs an id, so it is somewhere you arrive from the list rather than somewhere
you can be sent. It is shown as a step and is never a link.

Route resolution is checked across every screen — including that
`/understanding/disambiguate` belongs to *what I heard* rather than being a step
of its own, and that `/schemes/20` resolves to the last step rather than the
list, which needs testing precisely because it also starts with `/schemes`.

A note left in `lib/flow.ts` for whoever changes a navigation button next: this
list has to move with it.

---

## Done on 2026-09-12 — the stepper is bigger, and exists at every width

Three things were asked for. **Two of them were already true**, which is worth
recording because the report reasonably assumed otherwise: `useFlowSteps`
derives the current step from the pathname, so *"you are here"* already moved
by itself and already covered all four screens. Seeing it once on
`/understanding` makes it look pinned there.

The third was real, and so was a fourth nobody named.

**It was too small.** Type went 13px to 15px, the current step to semibold in
full ink, its dot from 7px to 13px with a ring around it, and the spacing
between steps roughly doubled. The connector is 2px now and **fills behind
you** — accent for ground covered, a hairline for what is ahead.

**It did not exist below 1536px.** That is most laptops and every phone: the
rail lives in the left gutter, and there is no gutter to live in at 1440. So
the flow simply vanished, which is worse than a stepper that changes shape —
nobody can learn to rely on something that appears on some screens and not
others. There is a compact horizontal bar under the header now, everywhere the
rail cannot fit.

Both read the same `useFlowSteps`. Two components working out which step is
current separately would drift, and the failure would be silent: a stepper
pointing at the wrong screen looks exactly like one pointing at the right
screen.

### Widening it was tried and reverted

Going to 150px pushes the requirement from 178px to 194px, and 1536 has 178.
The rail would have disappeared below 1728 — paying for a little more room with
most of the screens able to show it at all. The size came from type, weight,
dot and spacing, all of which fit inside 140px.

---

## Fixed on 2026-09-12 — a citation can carry a URL, and the verification gate is real

### Citations named a file nobody could look up

An answer drawn from a guideline cited `NLMGuidelinesJan2025.pdf`. The point of
a citation here is that a person can go and read the rule themselves, or take it
to an office — a filename does not do that.

`scheme_documents.source_url` had existed since `005`, but **only web-fetched
pages ever had one**: the ingest script never passed a URL for a local PDF, and
`match_document_chunks` did not return the column, so nothing downstream could
have used it. `db/009` returns it; the ingest script reads
`data/scheme_docs/sources.json`; the citation prefers it; both screens render it
as a link to the government's own page.

**The URLs are typed in by hand and never derived.** `websearch.py` consults no
model at all precisely so that it cannot invent an address, and a guessed
government URL looks exactly as official as a real one. `sources.json` ships
listing all twenty PDFs with empty values — an entry left empty is correct and
safe, and the citation falls back to naming the document, as before. A relative
path or a bare domain is rejected rather than repaired.

### A gate that was recorded and never enforced

Found while doing the above: **`scheme_documents.status` was written and never
read.**

A page fetched from outside the `.gov.in` family is stored
`pending_verification` so that an admin must approve it before the system
asserts anything from it. That is the entire point of the tiering in
`websearch.py`, `/api/admin/sources` exists to action it, and it is written up
in this file as the reason searching the web cannot quietly widen what the
system claims.

Neither retrieval path filtered on it. **A pending page was retrievable and
citable the moment it was stored, and rejecting one did not withdraw it.** Both
paths filter on `status = 'active'` now.

Nothing was actually exposed: every document in the corpus is active, so the
change removes nothing today. The gate simply starts working the first time a
non-government page arrives — which is exactly when it was always supposed to.

---

## Done on 2026-09-12 — the left gutter carries the flow

Three attempts at the empty sides had all been *decoration* — rings, a
waveform, margin rules. The note back was blunt and correct: put something
there, not another faint line.

So the left gutter now carries **where you are**. The product is four screens
with no breadcrumb between them — speak, what I heard, what fits, your passport
— and the person using it may not read the headings. On a phone that survives,
because each screen fills the view. On a monitor it was a centred column with
nothing either side.

The current step is marked, the ones behind it are links so you can go back and
change something, and a step you have not reached is not a link — offering it
would send someone to a screen with nothing on it. It appears only on the flow;
the landing page, About and admin are not steps in anything, and a progress
rail beside them would be claiming otherwise.

### It only appears at 1536px, and that is measured

| viewport | container | gutter | rail needs | |
|---|---|---|---|---|
| 1280px | 1101px | 90px | 178px | overlaps the text |
| 1440px | 1180px | 130px | 178px | overlaps the text |
| 1536px | 1180px | 178px | 178px | fits |
| 1920px | 1180px | 370px | 178px | fits |

A rail with readable text in it needs about 178px, and below 1536 the gutter is
narrower than that, so it would sit on top of the words. **An empty margin is
better than a rail over the text.** It is anchored to the content column rather
than the viewport, so the gap beside the words stays constant as the window
grows.

The decorative rule that was in the left gutter is gone; the right one stays,
from `lg` up, so the mid widths are not bare.

**Between 1280 and 1440 the sides are still margins.** There is no honest way
to put text in 90px. If those widths should feel fuller, the answer is a wider
content column, not more gutter content — and that is a different change.

---

## Done on 2026-09-12 — Ask takes typing, and the gutters are used

### The Ask panel had no way to type in most browsers

Reported against `/schemes/20`: the panel offers a microphone and nothing else.

It was **either/or** — `canListen ? <mic> : <text field>`. The text field
existed but only appeared when the browser *could not* listen, so in Chrome
there was no way to type at all. A noisy room, a quiet room, a shared phone, or
simply preferring to write all hit the same dead end.

One field now, with the microphone inside it, which is the pattern people
already know from every chat box. Both routes reach the same handler, so the
answer is identical either way.

**Speaking still sends as soon as the sentence ends.** The words appear in the
field as they are recognised, so a mishearing is visible and can be corrected
and asked again — but asking is not made to wait for a second tap. This product
is used by people who may not read the button they would have to find, and
adding a confirmation step after speech would cost them more than it gains.
That is the one acceptance criterion not met in full, and it is deliberate.

The separate preview bubble is gone: with the field always visible, two copies
of the same in-progress sentence, one editable, is confusing about which is
real.

### The sides were the emptiest part of a wide screen

The content is a centred column, so above about 1024px there is real space at
either edge doing nothing.

Margin rules run down both gutters now: a hairline that fades at both ends, so
it reads as the page having margins rather than as a line drawn on it, with
amplitude ticks along it — the waveform from the speak screen, stood on its
end, at rest.

Measured before drawing anything there. The gutter is 72px at 1024 and 90px at
1280, which is room for a rule 28px from the edge; below `lg` the content
reaches the edge and there is no gutter to decorate, so they are hidden.

---

## Done on 2026-09-12 — speech voices load at startup

Asked why the text appears and then the audio takes a moment to arrive.

Three costs were stacking, and only one was worth fixing. The answer and its
audio are **two separate requests** by design — the reply is put on screen and
the spinner stopped before synthesis is even asked for, because holding the
spinner "made a delivered answer look like a stalled one". So the wait is
visible by construction.

What made it long was that **the first synthesis in a language reads a 63 MB
ONNX graph**, and on a tier that sleeps after fifteen minutes idle that happens
again after every nap. It landed in the worst possible place: between a person
seeing a reply and hearing it.

Voices are loaded at startup now. Measured on the Tamil voice:

| | |
|---|---|
| voice load | **2.71s** |
| load again, cached | 0.000s |
| synthesis with a warm voice | 0.49s |

So a first spoken answer goes from roughly 3.2s to 0.5s.

**Not awaited.** A 63 MB read would delay the app reporting itself ready, and
the point is only to move it off the path of someone waiting. Whoever speaks
first is being recorded and transcribed while it runs, so it is normally
finished before any audio is asked for — and if it is not, `synthesize` loads
the voice the old way and nothing breaks.

**It does not reduce memory, only moves the read.** A container that never
receives a speech request now holds a voice it would not otherwise have loaded.
`TTS_WARM_LANGUAGES` defaults to `ta` alone — the interface default and the
language most of these users speak. All three would hold roughly 190 MB on a
512 MB tier.

Warming touches application startup, and a missing voice file is a *supported*
configuration — synthesis falls back to the browser's own speech, which is real
speech in the person's language. So `tests/test_voice_warming.py` pins the part
that could go wrong: the app starts when no voice exists, and when warming
raises outright.

---

## Done on 2026-09-12 — the About page reads across, not down

It was a 760px column of five stacked sections: correct, and very tall on a
monitor.

The title and the opening line sit **side by side** now rather than stacked,
which is where most of the height was going, and the five sections run in
**two columns** below them. The container widened from 760px to 1080px, matching
the schemes page.

**Two columns, and not before 1024px.** The width was measured rather than
guessed, because column count is the one layout decision that can quietly ruin
prose:

| viewport | column | characters a line |
|---|---|---|
| 1440px | 512px | ~68 |
| 1280px | 512px | ~68 |
| 1024px | 412px | ~55 |
| 768px | 302px | **~40** |

Comfortable reading runs from about 45 to 80 characters. Splitting at `md`,
which is the obvious choice and where this started, puts 768px at forty — the
width where reading turns into a newspaper column. So it splits at `lg` and
stays a single column below, and a third column was never an option because it
would put every width under forty.

---

## Done on 2026-09-12 — a backdrop, and the navbar centred

**The navbar links are centred and larger.** A three-column grid with equal
outer columns holds them in the middle of the *header* rather than the middle
of whatever space is left over — so they do not shift when the language switch
changes width between scripts, which it does between Latin and Tamil. Links
went 13px to 15px, the language buttons 12px to 13px with more padding, and the
wordmark 15px to 16px.

On a phone the grid collapses to two rows: wordmark and language switch on the
first, links centred underneath. Fitting all of it on one line at 360px would
mean type too small to tap accurately.

**A backdrop behind every page.** The screens are one column of content on a
flat cream field, which on a wide monitor reads as empty rather than calm.

Both marks are the product's own vocabulary rather than decoration borrowed
from elsewhere: **concentric rings are what the microphone does when it is
listening**, and **the waveform is what a voice looks like on the speak
screen**. Someone who has used it once will recognise both.

Kept almost invisible — the accent at four to nine per cent. The microphone is
where this product spends its boldness, and a backdrop that competed with it
would cost more than the flatness does. The rule written into the component: if
you notice these before you notice the mic, they are wrong.

Responsive in both directions. The rings scale with the viewport and crop
against its corner, because a complete circle reads as an object on the page
while a cropped one reads as the page having an edge. The waveform is hidden
below `md`: on a phone the content already reaches both edges, so it would only
be clutter behind the text.

Static SVG, no script and no animation. The target device is a cheap Android
phone, and ambient motion behind every screen is exactly what makes one feel
slow. `fixed`, so it does not repaint on scroll.

One trap avoided: the backdrop sits at `z-0` with the content at `z-10`, not at
a negative index. A negative `z-index` paints behind the parent's background,
and this body's background propagates to the canvas, which would have made it
depend on painting rules nobody should have to reason about.

---

## Done on 2026-09-12 — navigation, and an About page

**Home and About in the navbar**, on every public screen. Home exists even
though the wordmark already goes there, because a wordmark reads as a logo and
only some people know it is also a button. The current page is marked with
`aria-current` and shown in full ink.

The header **wraps instead of overflowing**. On a 360px phone the wordmark,
three links and the language switch do not fit on one line, and a header that
scrolls sideways is worse than one that takes two.

**Admin had no way back at all.** The public navbar hides itself there by
design — admin is a different product for a different person, and dressing it
like the beneficiary surface would blur a line the spec draws sharply — but
that left those pages with no route to the rest of the site. A single plain
`← voicepath` link now sits in the admin header, in admin's own register.

### `/about`

Five sections, in all three languages: who it is for, how it decides, what it
will not do, what happens to a recording, and where the information comes from.

Everything on it is true of the product and checkable against the code — that a
score is arithmetic rather than an opinion, that a skill is shown with the words
that produced it, that a recording becomes text and is discarded, that every
scheme answer names the document it came from.

**It makes no claim about who built it.** Inventing a team, an organisation or a
founding story would be the one kind of fiction this codebase exists to refuse,
and it is the same rule that stops an explanation claiming a skill nobody
mentioned. If the page should carry that, the details have to come from someone
who knows them.

---

## Done on 2026-09-12 — the landing page says what it is

The hero carried `flex-1`, so it absorbed every spare pixel of a tall screen.
That centred it beautifully and left the page empty above and below, with
nothing telling a first-time visitor what this was.

A section under the hero now explains it in three steps — speak, check what was
understood, see what fits — with a closing line saying what VoicePath does
**not** do:

> VoicePath does not apply for anything on your behalf. It tells you what
> exists, and what to say when you go.

That is the most useful sentence on the page for anyone who has dealt with a
government portal before, and it is the one thing the site could not say while
it had no room to say anything.

Written in all three languages, as everything in `i18n.ts` is — in each
language rather than translated out of the English.

Two deliberate restraints:

- **It is quiet.** The microphone is where this page spends its boldness, and a
  second loud element would compete with the one action anybody needs to take.
  A hairline rule, body type, no cards and no shadows.
- **The steps are numbered**, which is usually a generated-page tell, but this
  is genuinely a sequence and someone who reads slowly is told the order rather
  than left to infer it from position.

The hero is sized to its content now instead of stretching, so what follows is
visible without scrolling on a desktop and one short scroll on a phone.
`items-center` stays, because it aligns the microphone against the statement.

Also removed a duplicated comment left in `page.tsx` by the motion pass.

---

## Fixed on 2026-09-12 — six years read as two, and experience shown too late

Reported as *"years of experience not displaying on the skill passport card"*,
with three suggested causes: extraction not parsing it, a field-name mismatch,
or the card not rendering it. **None of the three was the problem.** Traced
end to end for the reported transcript:

```
extract  -> profile.experience_years = 5.0
passport -> profile.experience_years = 5.0
```

and that session is in the database with `years=5.0`. The passport renders it
at 38px. Nothing in that chain was broken.

Two real defects turned up underneath it.

### "two-wheelers for six years" was read as two years

The offline parser matched spelled-out numbers by **substring**, then accepted
any year word within 22 characters. So in *"repairing two-wheelers for six
years"* the "two" inside "two-wheelers" paired with the "years" belonging to
"six", and six years of experience became two.

A word boundary alone does not fix it — a hyphen is not a word character, so
"two" is already a whole word there. **Adjacency is the fix:** the number must
be its own word, and a year word must follow within one word. "five long years"
still reads; "two bikes" still reads as nothing, which is what the original
guard was written for.

This path is not a fallback curiosity. It runs whenever the model is
unavailable, and it was running in production while this was diagnosed, because
Groq's **daily** token allowance had run out.

### Experience was shown nowhere the person could check it

`experience_years` appeared in exactly one place in the entire frontend: the
passport stat tile, which a person reaches *after* matching. It was not on
`/understanding` — the screen that says *"Change anything that is wrong. Every
line shows the words you actually said."*

So experience is a quarter of a match score, the parser can misread it, and the
screen built for catching mistakes never showed it. It does now, with the
phrase it was read from, and says plainly when no duration was heard.

**It is still not editable.** Correcting it means re-recording, because no
endpoint edits a stored profile. Seeing that it is wrong is the half that was
missing; that is on the to-do list.

### Why it is not on the skill card

The report asked for it there. Experience is stored once per profile, not per
skill — there is no per-skill duration anywhere in the model. Putting the
profile figure on each card would claim five years of welding for someone who
said five years of plumbing and a little welding, which is exactly the kind of
unearned attribution this codebase refuses everywhere else. Per-skill durations
would be a real feature: prompt, schema, migration and UI.

---

## Fixed on 2026-09-12 — off-topic typing became a skill card

Reported from the deployed app: typing *"desire doue or ousmane dembele ?"* on
the understanding screen produced a skill card titled with those words, flagged
*"I am not fully sure about this one"*, and let the person carry on to their
matches.

**This was a defect in the typed box added hours earlier, not in the pipeline.**
The spoken path never had it: extraction reads a transcript and returns nothing
for football players, so an off-topic recording lands on the empty state.
Verified against the live model — that input yields zero skills, and intent
classifies it `work=False, question=True`.

The typed box skipped extraction and went straight to normalization, which
answers a different question: *which taxonomy node is this nearest?* And e5
answers that for anything. Measured against the live taxonomy:

| typed | similarity | became |
|---|---|---|
| `desire doue or ousmane dembele ?` | 0.7528 | uncertain skill |
| `who is the prime minister` | 0.7568 | uncertain skill |
| `asdfghjkl` | 0.7795 | uncertain skill |
| `carpentry` | 1.0000 | Carpentry |

All three clear the 0.60 candidate threshold. **This is the third place the
same property has had to be handled** — matching scored every scheme 86-95,
retrieval scores "asdfghjkl" at 0.794 against the corpus, and now this. e5 has
no concept of "unrelated", only of "nearest".

The landing page already stated the rule the box broke: typing "joins the
pipeline at exactly the point speech does: the transcript". It does now.
`POST /api/profile/skills` classifies the text with the same step that routes
speech, and has three answers rather than two:

- **work** — extracted exactly as from speech, so each skill still carries
  evidence quoted from what was typed and `_validate` still drops what it
  cannot find there.
- **a question** — *"who is eligible for PM-AJAY"* is not work, but refusing it
  would be wrong. It is handed back and answered by the panel already on the
  screen.
- **neither** — refused, nothing stored, and the reason shown beside the field
  in amber rather than red. Typing something unusable is a normal part of being
  asked an open question, not an error the person committed.

Extraction is the arbiter for the work case rather than classification alone,
because it is what reads the text and finds no trade in it. Checked that it
does not over-reject short input: *carpentry*, *welding*, *bike repair*,
*I stitch clothes*, *tailoring work* and *lorry driving* each yield one skill.

---

## Done on 2026-09-12 — the understanding screen takes typed skills

Every route into this product ended at the microphone. `/understanding` offered
*"say something more"* beside the cards and *"say it again"* when nothing was
found, and both went to `/speak`. Someone in a noisy room, on a shared phone,
or whose trade had just been misheard had nothing else to try — and being
misheard is exactly the known weakness, since Whisper mishears English
loanwords inside Tamil.

A text field now sits in both places: under the cards when skills were found,
and beneath the empty state when none were. The empty state is the one that
matters most — speech has already failed for that person once, and offering
only the microphone again is the least useful thing the screen can do.

**The microphone keeps its place first**, here as on the landing page. Typing
is the second way in, not a replacement and not a lesser one.

**What the person types is the evidence.** Every card shows back the words that
produced it, and for a typed skill those are the words they typed — not a quote
lifted from the spoken transcript, which would attribute the wrong thing to
them. This is the rule the landing page already follows, where typing "joins
the pipeline at exactly the point speech does: the transcript".

**Typing is a way in, not a way around.** A typed skill is normalized like any
other: exact alias, then embedding, then the disambiguation screen when it is
not clear enough. `tests/test_typed_skill.py` pins both halves — that a skill
carrying no id is accepted and does not displace the ones already there, and
that "asdfghjkl" typed in resolves to no taxonomy skill at all.

No backend change was needed. `/api/profile/normalize` already took a full
corrected list and already treated `id` as optional; the interface simply never
used it.

---

## Done on 2026-09-12 — the corpus says what it is

Three documents were stored under hashes, and a citation shows the source
filename to the person reading the answer. Somebody asking about ITI training
was being told the claim came from `6d3fed46d8d6c01f6035291880f3213c.pdf`,
which is no better than showing them nothing.

Identified from their own first pages and renamed:

| was | is |
|---|---|
| `240a33870657b8ddc72d8d835b5f6823.pdf` | PMGSY — road connectivity for Left Wing Extremism affected areas (2017) |
| `6d3fed46d8d6c01f6035291880f3213c.pdf` | PM SETU — upgradation of ITIs, Component I guidelines |
| `71441776233188.pdf` | Ministry of Social Justice and Empowerment, Annual Report 2025-26 |

The two scanned files were dropped: `8509766cf8cc0c490eb25299f0fbc9af.pdf`
(10MB) and `2109-Pushpanand-Shankarrao-Nitanvare-Order.pdf`, which is a court
order rather than a scheme document. Both extracted zero characters and were
skipped at ingest, so they carried 10MB of repository weight for nothing.
22 files and 37MB down to 20 and 28MB.

Renaming a file orphans its rows, because `source` is the filename and
`retrieval.ingest` replaces by it. The three stale documents were deleted and
their files re-ingested under the real names, then the corpus was reconciled
against the directory in both directions: **no document stored under a name
that is not on disk, and no PDF on disk that is not in the corpus.** 21
documents and 1096 passages, unchanged in content.

### The two NHDP schemes, disambiguated

`nhdp.pdf` was the National **Handicrafts** Development Programme and `Final
Revised  Guidelines NHDP 12.04.2023.pdf` the National **Handloom** Development
Programme -- different schemes sharing an acronym, with a double space in the
second filename. An artisan asking about handicrafts could be shown a handloom
citation with no way to tell them apart. They are now
`NHDP_Handicrafts_Guidelines_2021-26.pdf` (110 passages) and
`NHDP_Handloom_Revised_Guidelines_2023.pdf` (139), and the corpus reconciles
against the directory in both directions.

---

## Done on 2026-09-12 — the full scheme corpus, and two defects found ingesting it

Nineteen more scheme PDFs were added to `data/scheme_docs`, taking it to 22
files and 37MB. The corpus now holds **21 documents and 1096 passages**, up
from 4 and 121.

Two of the twenty-two extract **zero characters** -- they are scanned images,
and the ingest script skips them rather than storing empty documents. One of
those, `2109-Pushpanand-Shankarrao-Nitanvare-Order.pdf`, also looks like a
court order rather than a scheme document. Neither contributes anything without
OCR.

### The chunker was discarding three quarters of the largest new document

`Startup-Schemes-Playbook-June-2026.pdf`: 188,000 characters, **24 chunks**.
The blocks being thrown away were the scheme descriptions themselves -- *"ADITI
is a government program that supports startups and innovators in building new
defence technologies..."* -- dropped as though they were navigation menus.

`_is_prose` rejected any block under six words a line. That was calibrated
against government *portal pages*, where a menu runs two to four words a line
and the prose beside it fifteen and up. A designed PDF wraps prose short inside
cards, so real content measured 5.3 and was cut.

Replacing the line test with sentence-ender density was also wrong, and was
caught before shipping: it cut a department's vision statement at 0.29 endings
per 100 characters, indistinguishable from a contents page, because government
prose runs to very long sentences.

**The fix is that either signal suffices.** A block that wraps long is prose. A
block that wraps short but ends sentences at a normal rate is also prose. Only
a block that does neither is furniture. Requiring both was the bug.

944 → **1094** chunks offered, the playbook going 24 → 93, with contents pages,
annexure lists and scoring tables still correctly excluded. The tests use real
extracted blocks saved as fixtures under `tests/fixtures/`, because two
hand-written "faithful" samples landed at 6.0 words a line and passed a filter
that rejected the real thing at 5.3.

### A rate-limited model was asserting unrelated passages

Asking *"What is the capital of France?"* against the new corpus returned
`grounded=True` and a passage about the Ambedkar International Centre.

Retrieval was not at fault. Groq answered **429 Rate limit reached**, and the
handler for that fell back to "return the best passage, grounded, with its
citation". That shape is a considered trade when there is no model *by design*
-- nothing can summarise, so the citation is the answer. Reused for a transient
failure it removes the only judge the module has and then asserts anyway, and
e5's narrow band guarantees there is always a confident-looking passage to
assert.

A transient failure now refuses. Deliberate offline operation is unchanged,
and a test pins that distinction.

### Known operational limit

Groq's free tier allows **7000 input tokens per minute**, and one question
sends five passages -- roughly 2500 tokens. That is about two or three
questions a minute across the whole deployment, shared by every user. It was
hit three times while testing seven questions in a row. Worth knowing before a
demo; the fix is a paid tier or fewer passages per question, and it is a
configuration decision rather than a bug.

---

## Fixed on 2026-09-12 — results are filtered on evidence, not just ordered

Follow-up to the scoring fix, from the obvious next question: *why did Pharma
Business and Plumbing Works score exactly the same for a carpenter?*

Because every component input was identical. Neither declared any skills (both
took the neutral 0.5), both asked one year against a stated three (1.0), neither
required certificates (1.0), and no location was given (0.5). There was nothing
to tell them apart, so nothing did.

**The obvious fix was measured and rejected.** Reading the scheme's own title
and description instead of its declared skills gets it backwards: embedding
each scheme's text and probing with Carpentry ranks *Pharma Business* (0.8162)
**above** *Plumbing Works* (0.8079), and probing with Plumbing itself clears
Pharma by only 0.02 — the same narrow band that caused the original bug.
Inferring requirements from free text would have made the ranking confidently
wrong rather than honestly flat, so it was not added.

**Two real fixes instead.**

The catalogue was completed: `Pharma Business` requires Retail Sales,
`Plumbing Works` requires Plumbing. Every active scheme now declares at least
one skill, which is the mechanism matching actually reasons over.

And `skill_evidence` was added to `ScoredMatch` — true only when a scheme
declares requirements *and* this person earned at least `SKILL_EVIDENCE_AT`
(0.05) against them. Not simply "more than zero": the similarity floor is a
measurement, and the closest unrelated pair measured sits 0.0007 above it,
rescaling to 0.009. The threshold clears that slop while admitting a genuine
neighbour at 0.34.

`/schemes` shows only results carrying that evidence. A scheme declaring no
skills cannot be *ruled out*, which is not the same as fitting, and a scheme in
another trade scores nothing on skill — but both still collect experience,
eligibility and distance, so both sat on the page at a plausible-looking
number. None of that is why someone comes here. When nothing carries evidence
the existing empty state says so, which is a truer answer than a list of near
misses.

The flag changes no score and is computed in `matching`, where the knowledge
is; what to do with a result that lacks it stays the interface's decision.

Measured against the live catalogue afterwards:

| input | shown |
|---|---|
| carpenter, 3 years | nothing — *"Nothing here fits your work yet."* |
| two-wheeler mechanic, 6 years | Two-Wheeler Training 79, Technician 73, Workshop 67, Auto Electrician 62 |
| plumbing, 2 years | Plumbing Works 95, an exact match |

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
