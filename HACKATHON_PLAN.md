# VoicePath — Jury Plan

**Theme:** transparency. Not a feature we added — the shape of the system.

The through-line for every part: **we don't ask you to trust the model. We show
you what it saw, what it inferred, and what it was structurally prevented from
doing.**

This is a presentation plan, not a code change. Nothing here restructures the
project.

---

## The one-sentence pitch

> Someone describes their work out loud — in Hindi, Tamil or English — and
> VoicePath extracts the skills, maps them to a standard taxonomy, matches them
> to real district openings, and explains every match using only what the person
> actually said, with a ranking that is arithmetic rather than opinion.

---

## The seven parts

Each part is one transparency claim, one thing to show live, and one artefact
that makes it evidence rather than assertion.

**Demo in Hindi as the default.** It is the widest reach for a national scheme,
and it is measurably the strongest language in the pipeline. Switch to Tamil and
English during the demo to show the same machinery works across scripts.

### 1. Voice in, words out

**Claim:** the system never acts on words you have not seen.

**Show:** speak on `/speak`. The transcript appears verbatim before anything is
inferred from it.

Measured, same pipeline, three languages:

| Spoken | Heard |
|---|---|
| "मैं पाँच साल से वेल्डिंग का काम करता हूँ।" | near-perfect |
| "I worked as a welder for five years in Coimbatore." | exact |
| "எனக்கு ஆறு வருஷமா பைக் ரிப்பேர் தெரியும்." | good, loanwords weaker — see Weak spots |

**Evidence:** `db/001_schema.sql:128`

```sql
constraint sessions_audio_url_requires_optin check (
  audio_retained or audio_url is null
)
```

Raw audio cannot be stored unless the person opted in — enforced by Postgres,
not by application code remembering to. Open the file and show the constraint.

---

### 2. Language is not a translation layer

**Claim:** three languages, each written natively, not translated from English.

**Show:** the language toggle. The Hindi and Tamil copy in `lib/i18n.ts` was
written in each language, not machine-translated from the English original.

**Evidence:** the system handles code-mixed speech the way people actually
speak — "engine mechanic-a velai paarthen", "वेल्डिंग का काम" — because
extraction runs on the source-language transcript. We never translate first,
because translating would throw away exactly the detail this platform exists to
handle. Place names resolve across scripts: "சேலத்துல" and "सेलम में" both match
a Salem opening.

**Known gap, say it first:** place names still *render* in English inside
non-English sentences. Matching resolves them correctly; only the display label
is untranslated.

---

### 3. Every skill carries the words that produced it

**Claim:** nothing is attributed to a person that they did not say.

**Show:** `/understanding`. Each card displays its `evidence_phrase` — the actual
words spoken, in the language they were spoken in. Edit one. Remove one.

**Evidence:** `extraction._validate` checks every quoted phrase against the
transcript and **drops the skill** if it cannot find it. A model that invents a
quote loses that skill entirely. `tests/test_extraction.py` covers Hindi, Tamil
and English.

Worth demonstrating: extraction catches skills people *describe*, not just ones
they name. From a Tamil sentence it produced "diagnosing engine problems by
sound" — the person never used a skill noun. No keyword search finds that.

---

### 4. Your words became a standard code — here is the score

**Claim:** the leap from speech to a formal skill code is visible and
challengeable.

**Show:** the disambiguation screen, with real measured numbers:

| Query | Matched | Score |
|---|---|---|
| "welding" (English) | `SK022 Welding` | **0.896** |
| "இன்ஜின் சத்தம்... கண்டுபிடிக்கிறது" (Tamil) | `SK014 Engine Diagnostics` | **0.836** |
| "इंजन मैकेनिक" (Hindi) | `SK014 Engine Diagnostics` | high |

**Evidence:** thresholds are **0.82 to accept, 0.60 to offer as a candidate**.
Below 0.60 the system asks rather than guesses, and "leave it out" is a real
answer.

The cross-lingual point is the one to land: Hindi and Tamil phrases match an
**English** taxonomy because all three embed into the same vector space. One
taxonomy, any language in.

Say the number out loud. A score against a stated threshold is a falsifiable
claim; "the AI understood you" is not.

---

### 5. The match score is arithmetic, not opinion

**Claim:** the ranking is reproducible, auditable, and contains no model
judgement.

**Show:** `/opportunities` and the score breakdown bars.

**Evidence:**

```
0.50 x skill  +  0.25 x experience  +  0.15 x eligibility  +  0.10 x location
```

**`services/matching.py` imports no LLM.** Same profile, same catalogue, same
ranking, every time — in every language. Ties break on id.
`tests/test_matching.py` asserts it.

**This is the strongest moment in the demo.** For a scheme allocating
opportunities to Scheduled Caste beneficiaries, "why was I ranked fourth?" needs
an answer that survives an audit. Most teams will have a model deciding. Point
at the file and say it cannot.

---

### 6. The explanation cannot change the ranking

**Claim:** the model that writes the reasons has no route back to the score.

**Show:** the reason bullets on a match card, then switch language — the same
match re-explains in Hindi, Tamil or English while the ranking stays identical.
That contrast *is* the point: the words change, the arithmetic does not.

One real bullet warned that a tailoring role expects sewing experience the
person did not have. It talks the user *out* of a match when the data says so.

**Evidence:** `explain()` returns `{bullets, summary, provider}`. **There is no
field through which a score could travel back.** The constraint is structural,
not an instruction the model is asked to follow, and it is handed a closed set
of grounding facts rather than the profile.

The line to rehearse: *"we constrained the interface so the failure is
impossible, rather than instructing the model and hoping."*

---

### 7. The system never pretends

**Claim:** when something is degraded, it says so — everywhere.

**Show:** `/health` in a browser tab.

```json
{"stt":"groq","tts":"local","llm":"groq","embeddings":"hf_api","ner":"offline",
 "degraded":["ner"]}
```

Every provider named. Then `/admin/sessions`: counts, scores, languages —
**no transcripts.** Operators audit usage without reading what people said.

**Evidence:** every provider has an offline implementation and the app downgrades
automatically. Offline mode is never disguised: `/health`, the response bodies
and a UI banner all say so, in the user's own language. Offline extraction finds
skills a person *names* but not ones they *describe* — a recall limit, never a
precision one.

---

## Plan to execute

It is the night before. Everything below is optional; the demo works without
all of it. Ranked by payoff per minute.

### Tier 1 — do these (about 65 minutes)

- [ ] **Surface the confidence number in the UI** (~30 min)
      Already in the API response and currently invisible. A juror seeing
      `0.836 · accepted (threshold 0.82)` understands the entire system at a
      glance. Highest payoff on the list. *Supports Part 4.*

- [ ] **Print the weights beside the score bars** (~15 min)
      Turns a pretty chart into a verifiable formula. *Supports Part 5.*

- [ ] **Rehearse the running order below, out loud, twice** (~20 min)
      More valuable than any code you write tonight. Practise the language
      switch — it is the moment that carries Parts 2 and 6 together.

### Tier 2 — if time allows (about 50 minutes)

- [ ] **Transcript view on `/understanding`** (~30 min)
      Full transcript with each evidence phrase highlighted in place. The offset
      logic already exists in `services/ner.py`. *Supports Part 3.*

- [ ] **Seed a few more opportunities** (~20 min)
      16 is visibly a demo. Even 30 changes the impression. Use
      `/admin/opportunities`.

### Tier 3 — do not attempt tonight

- RAG over policy documents — worth building, wrong night
- IndicWav2Vec for Tamil ASR — real fix, not a two-hour job
- Wiring NER into the pipeline
- Anything that touches `matching.py`

**Rule for the night:** if a change is not finished and verified by your cutoff,
`git checkout .` and present what works. A broken demo costs more than a missing
feature.

---

## Demo running order (8 minutes)

| # | Beat | Language | Time | Part |
|---|---|---|---|---|
| 1 | Speak on `/speak`; transcript appears verbatim | **Hindi** | 1:00 | 1 |
| 2 | `/understanding` — evidence on every card; edit one | Hindi | 1:30 | 3 |
| 3 | Show a confidence score against its threshold | Hindi | 1:00 | 4 |
| 4 | `/opportunities` — breakdown bars, state the formula | Hindi | 1:30 | 5 |
| 5 | Open a match; read a reason; note the honest warning | Hindi | 1:00 | 6 |
| 6 | **Toggle to Tamil, then English** — reasons re-explain, ranking identical | all three | 0:30 | 2 + 6 |
| 7 | `/health` and `/admin/sessions` | — | 1:00 | 7 |
| 8 | Close: the boundary you drew and why | — | 0:30 | — |

Beat 6 is the one to nail. It proves the multilingual claim and the
"explanations cannot re-rank" claim in a single gesture.

**Closing line:**

> We use a language model to read and to explain. We do not use one to decide.
> The ranking is arithmetic, the evidence is verified against what was said, and
> the audio is gone. Transparency is not a screen we added — it is the reason
> the architecture looks like this.

---

## Pre-flight checklist

Run through this an hour before, not five minutes before.

- [ ] `git push` — the TTS fix and the language-switch fix are committed but may
      be unpushed
- [ ] Vercel deployment is green and the production URL loads
- [ ] `curl https://voicepath-api.onrender.com/health` returns `"degraded":[]`
      (or only `["ner"]`)
- [ ] **Wake the backend 10 minutes before you present.** The free tier sleeps
      after ~15 minutes idle and the first request takes ~30s
- [ ] Microphone permission already granted in the demo browser
- [ ] **A sentence prepared and practised in each language** — Hindi for the main
      run, Tamil and English for the switch
- [ ] Second tab open on `/health`
- [ ] Editor open on `services/matching.py` for the Part 5 moment
- [ ] Phone hotspot ready — venue wifi fails
- [ ] Laptop charged; localhost fallback ready if the network dies entirely

---

## Weak spots — say them before the jury finds them

Naming your own failure modes reads as rigour. Being caught reads as the
opposite.

**Tamil mishears English loanwords.** "வெல்டிங்" (welding) came back as
"வெள்ளி" (silver), and the pipeline then faithfully reported *silver work* —
grounded in a transcript that was itself wrong, which is the one failure
evidence-verification cannot catch.
*Answer:* we found it, measured it at two model sizes both locally and hosted,
and the fix is a Tamil-specific model — AI4Bharat's IndicWav2Vec. **Hindi and
English do not have this problem**, which is why the main demo runs in Hindi.

**Only 16 opportunities, and they are seeded.**
*Answer:* seed data for Salem and Erode. `data.gov.in` publishes district-level
skilling catalogues under GODL-India, and the admin importer already accepts
them.

**The first request is slow.**
*Answer:* free-tier hosting sleeps when idle. Deliberate — the whole stack runs
at zero cost, which matters for a scheme meant to run on district budgets.

**Entity tagging is offline.**
*Answer:* built and degrades safely, not yet wired into the pipeline. `/health`
says so rather than hiding it — which is the point of Part 7.

---

## If a juror pushes on "where is the AI?"

Do not get defensive. The boundary *is* the answer:

> Four models run in this pipeline. Whisper transcribes Hindi, Tamil and
> English. Qwen extracts skills from natural speech — it caught "diagnosing
> engine problems by sound", which no keyword search would find.
> multilingual-e5 maps a phrase in any of the three languages onto one English
> taxonomy. Piper speaks the answer back in the user's own language.
>
> What no model does is decide the ranking. That was a choice, and it is the one
> we would defend hardest.
