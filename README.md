# VoicePath

Voice-first skill discovery and scheme matching for Scheduled Caste beneficiaries
under the PM-AJAY skilling ecosystem.

Someone describes the work they have done, out loud, in Tamil, Hindi, English or a mix
of them. VoicePath extracts the skills, normalizes them against a standard taxonomy,
matches them to real district-level openings and training, and explains every match in
plain language — using only what the person actually said.

**See `STATUS.md` for the live build state and task checklist.**

---

## Running it

Two processes: a FastAPI backend and a Next.js frontend. Everything except the
LLM runs locally, so the one-time setup downloads models rather than handing out
keys.

### Backend

```bash
cd backend
pip install -r requirements.txt      # API only; speech falls back to the browser
pip install -r requirements-ml.txt   # local Whisper, Piper and embeddings (~3GB)
python -m app.scripts.fetch_voices   # Piper voices for ta/hi/en (~190MB)
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```

`http://localhost:8000/docs` for the API, `/health` for what is actually live.

The first transcription after a restart spends ~60s loading Whisper into memory;
it is cached from then on.

### Frontend

```bash
cd frontend
npm install
cp .env.local.example .env.local
npm run dev
```

`http://localhost:3000`. Start the backend first, or at least before opening
`/speak` — the frontend fetches `/health` once on load and does not retry, so a
backend that arrives late leaves the microphone disabled until you reload.

If port 3000 is busy Next silently moves to 3001. `CORS_ORIGINS` allows 3000-3002
for exactly that reason; a port outside that list looks identical to a dead
backend from the browser's side.

### Database (optional)

Without `DATABASE_URL` the API keeps sessions in memory and serves the catalogue from
`backend/app/data/catalogue.py`. The whole pipeline works; nothing survives a restart.

With Supabase, apply `db/001` … `db/004` in order (see `db/README.md`), then:

```bash
cd backend && python -m app.scripts.embed_taxonomy
```

Add `--all` to recompute vectors that already exist — needed after changing
`EMBEDDING_MODEL`, and after switching off the offline hashing fallback. Without
it the script only fills in missing rows and silently leaves stale vectors in
place.

---

## The stack, and what it costs

Every component except the LLM runs on the machine. No speech vendor, no
per-call cost, and nothing about a person's voice leaves the process.

| Layer | Component | Licence | Runs |
|---|---|---|---|
| Speech-to-text | faster-whisper (`medium`, int8) | MIT | Locally, on the CPU |
| Text-to-speech | Piper | MIT — **Tamil voice is CC-BY-4.0** | Locally, on the CPU |
| Embeddings | `multilingual-e5-base` | MIT | Locally, on the CPU |
| Entity tagging | `ai4bharat/IndicNER` | MIT | Locally — **gated repo, needs an HF token** |
| Extraction / explanation / Q&A | Groq-hosted open-weight models | Open weights, hosted service | Over the network |

The LLM is the one exception, and it is a deliberate one: an open-weight model
(`qwen/qwen3.8-27b` by default) hosted by Groq. The weights are open source; the
hosting is not. A local model was measured at 1-3 minutes per extraction on a
laptop CPU against Groq's ~2 seconds, and this is a tool for people standing in
a queue.

### Keys

One key, `LLM_API_KEY` in `backend/.env`, free from
[console.groq.com/keys](https://console.groq.com/keys).

`HF_TOKEN` is needed only for entity tagging: `ai4bharat/IndicNER` is a gated
repo, so you must accept its terms on huggingface.co first. Without it NER
returns nothing and the rest of the pipeline is unaffected.

`.env` is gitignored. `.env.example` is committed, so never put a real key in it.

**Groq rotates its model lineup.** If `LLM_MODEL` starts returning 404, list
`https://api.groq.com/openai/v1/models` and pick a current one.

### Running without any key

The app still runs. `LLM_PROVIDER` drops to `offline`, and extraction falls back
to a lexical pass over the transcript. It never pretends: `/health`, every
response body, and a banner in the UI all say which providers are offline.

Offline extraction finds skills a person **names** ("welding") but not ones they
only **describe** ("I join metal pipes"). That is a recall limit, never a
precision one — no offline path can assert something the person did not say.

### Known limit: Tamil speech recognition

Whisper's Hindi is excellent and its Tamil is not. It mishears English loanwords
inside Tamil speech, and the failure is worse than a dropped word: "வெல்டிங்"
(welding) came back as "வெள்ளி" (silver), and the extraction layer then
faithfully reported *silver work*, grounded in a transcript that was itself
wrong. Evidence verification cannot catch this — the quote really is in the
transcript.

Tested at `medium` and `large-v3`, local and Groq-hosted, with the same result,
so it is a property of the model family rather than of the deployment. If this
matters for your users, AI4Bharat's IndicWav2Vec (Apache 2.0, not gated) is the
Tamil-specific alternative.

---

## Layout

```
db/          Schema, functions, seed and RLS. Apply in numeric order.
backend/     FastAPI. Routes are thin; the pipeline lives in app/services/.
frontend/    Next.js App Router, TypeScript strict, Tailwind v4.
```

### The pipeline

```
audio ──▶ transcript ──▶ profile + skills ──▶ taxonomy ids ──▶ ranked matches ──▶ text
         (STT)          (LLM extraction)     (embeddings)      (deterministic)   (LLM)
                              │                                       │             │
                     evidence verified                        no LLM here     cannot re-rank
                     against transcript
```

---

## The three rules the code enforces

The PRD names these as non-negotiable. Each is a property of the system, not a request
made of a model.

**1. Extraction never invents.** The prompt says so, and then
`extraction._validate` checks every `evidence_phrase` against the transcript and drops
what it cannot find. A model that quotes something never said loses that skill entirely.
`tests/test_extraction.py`.

**2. Ranking is deterministic.** `services/matching.py` imports no LLM. The same profile
against the same catalogue produces the same ranking every time, ties break on id, and
the numbers are reproducible from the stored `matches` row. `tests/test_matching.py`.

**3. Explanations cannot re-rank.** `explain()` returns `{bullets, summary, provider}` —
there is no field through which a score could travel back. It is given a closed set of
grounding facts, not the profile. `tests/test_explanation.py`.

And one more, from §7: **raw audio is not kept.** The `sessions` table has a check
constraint making `audio_url` non-null only when the user opted in, so the rule holds at
the database level and not only in application code.

---

## Tests

```bash
cd backend && python -m pytest        # 178 tests
cd frontend && npx tsc --noEmit && npx next build
```

The suite runs entirely offline — no keys, no network, no database. The guarantees being
tested belong to this code, so a test that needed a vendor to demonstrate them would be
testing the wrong thing.

---

## Adding to it

Read PRD §6 first. In short:

- **Data first.** `skill_taxonomy` and `schemes` are the source of truth. Never
  hardcode a skill list or an scheme in a component.
- **Style through tokens.** Everything is named in `frontend/app/globals.css`. No
  hardcoded colours in pages — the visual direction is meant to be revisable without
  touching extraction, normalization or matching.
- **Server components by default.** `"use client"` only for interactivity: the mic, the
  waveform, editable fields.
- **Keep the LLM boundaries.** Extraction may not invent; explanation may not re-rank.
  Any change that blurs those needs explicit review.
- **Adding a skill** means editing both `db/003_seed.sql` and
  `backend/app/data/catalogue.py`, plus a Tamil and Hindi label in `DISPLAY_NAMES`.
  `tests/test_catalogue_sync.py` and `tests/test_localization.py` fail if you miss one.
