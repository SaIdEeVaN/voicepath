# VoicePath — Jury Q&A

Answers grounded in what is actually built. Where something is not built, it
says so — a jury forgives a known gap and punishes a bluff.

**Numbers worth memorising:** weights `0.50 / 0.25 / 0.15 / 0.10` · thresholds
`0.82` accept, `0.60` candidate · `178` tests · `44` taxonomy skills ·
`16` opportunities · extraction `~1.9s` · embedding dimension `768`.

---

# Round 1 — Technical Architecture

### Q1. Why an LLM for extraction instead of NER or keyword matching?

Because people describe work; they rarely name it. "எங்க மாமா கடையில இன்ஜின்
சத்தம் கேட்டா பிரச்சனை தெரியும்" contains no skill noun at all, and our model
extracted *"diagnosing engine problems by sound"* from it. No keyword list finds
that, and NER would not either — NER tags entities: people, places,
organisations. "I fix bikes for my uncle" has no entity that maps to
two-wheeler repair.

We still use NER, but for what it is actually good at: places, employers,
durations. It supports extraction; it cannot replace it.

### Q2. How do you enforce "the AI cannot invent skills"?

Every extracted skill must carry an `evidence_phrase` — the exact words from
the transcript, character for character, in the language spoken. Then
`extraction._validate` searches the transcript for that phrase. **If it is not
there, the skill is dropped entirely.**

So a hallucinated skill does not get flagged or downweighted — it disappears,
because the model could not produce a quote to justify it. The prompt asks;
the code enforces. `tests/test_extraction.py` covers this in all three
languages.

### Q3. Why not let the LLM rank the jobs?

Because this decides who gets told about which livelihood opportunity under a
government scheme. If someone asks "why was I ranked fourth?", the answer has to
be reproducible and auditable a year later.

`services/matching.py` imports no LLM. Same profile, same catalogue, same
ranking, every time. Ties break on id. An LLM ranking is not reproducible, not
explainable in a way that survives an audit, and not defensible if someone
alleges bias.

### Q4. Explain the 50/25/15/10 weights.

```
0.50 skill  +  0.25 experience  +  0.15 eligibility  +  0.10 location
```

- **Skill (0.50)** — cosine similarity between the person's normalised skills
  and the opportunity's required skills. Half the weight, because skill match is
  the thing the platform exists to determine.
- **Experience (0.25)** — stated years against the opportunity's minimum.
- **Eligibility (0.15)** — certifications required versus held.
- **Location (0.10)** — resolved to district, with a town→district map so
  someone in Attur is near Salem, not equidistant from Kolkata.

Honest framing: the weights come from the PRD, and they are *tunable* —
environment variables, validated to sum to 1.0. We are not claiming they are
empirically optimal. We are claiming they are **visible and auditable**, which
an LLM's judgement is not.

### Q5. "I know bike repair, but I only helped my uncle occasionally." Professional vs casual vs experience?

Partially handled, and I will be precise about where the line is.

The prompt's rule 4 is *flag uncertainty, do not resolve it*. In our own testing,
"மாமா கடையில" produced the flag *"unclear whether this was paid employment or
unpaid assistance"* — and `experience_years` stayed null rather than being
guessed. Hedges like "கொஞ்சம்" (a little) surface as uncertainty flags too.

What we do **not** have is a formal proficiency scale. We do not grade casual
versus professional; we surface the ambiguity to the user on `/understanding`,
where they can correct or remove it. That is a deliberate choice — a guess that
looks like a fact is more harmful here than a gap the person can fill.

A proficiency dimension is a real next step.

### Q6. "I don't know welding, but my friend does welding." — how do you avoid extracting Welding?

**This is our weakest guarantee, and I would rather say so.**

The evidence check does not save us here: the word "welding" *is* in the
transcript, so a quote exists. The prompt's rule 1 — extract only what is
stated, about this person — is what has to catch it, and prompt rules are not
guarantees the way `_validate` is.

What limits the damage: extraction output is never used silently. Every skill
appears on `/understanding` as an editable card showing the words that produced
it. The person sees "welding — *my friend does welding*" and removes it. Nothing
reaches matching until they confirm.

The proper fix is attribution parsing — first-person versus third-party, and
negation — which is exactly what a transformer NER layer plus a dependency parse
would give us. That is in the plan, not in the demo.

### Q7. Why multilingual embeddings? What breaks with an English-only model?

Our taxonomy is in English. Our users speak Tamil and Hindi. An English-only
model has never seen Tamil script — the vectors would be noise, and nothing
would ever cross the 0.60 threshold.

We know precisely what that failure looks like, because we hit it. Before we
switched to `multilingual-e5-base`, the taxonomy held hash-based fallback
vectors and every skill scored **0.12–0.48** against a 0.60 candidate threshold.
Nothing normalised. With the real model, the same inputs score **0.78–0.90**.

### Q8. Tamil → taxonomy → embedding → opportunity: what happens mathematically?

The Tamil phrase and the English taxonomy entry are each mapped by
`multilingual-e5-base` into the same **768-dimensional** space. The model was
trained so that text with the same *meaning* lands in the same region regardless
of language — so "இன்ஜின் மெக்கானிக்" and "Engine Diagnostics" end up near each
other despite sharing no characters.

Both vectors are L2-normalised, so cosine similarity reduces to a dot product.
pgvector's `<=>` operator computes cosine distance inside Postgres; we take
`1 - distance` as similarity and compare it against the thresholds.

The opportunity's required skills carry taxonomy ids, so once the person's words
have an id, matching is set arithmetic on ids — no language involved at all.

### Q9. Why exact alias matching before embeddings?

Because a taxonomy node's embedding is the average of roughly a dozen aliases,
so it sits in the *centre* of that cluster. An exact hit on one alias therefore
scores **lower** than its exactness deserves — the vector has been diluted by
its siblings.

If someone says the precise term, that is stronger evidence than any similarity
score. So exact alias wins first.

Deliberately **exact, not substring** — otherwise "welding certificate" would be
silently upgraded to "welding", which is a qualification the person never
claimed.

### Q10. Motorcycle Repair 0.91, Electrical Repair 0.89, Welding 0.87 — is 0.87 good enough?

By our thresholds: 0.87 is above **0.82**, so it is accepted. But your question
exposes something real, and I would rather name it.

`e5` compresses similarity into a narrow high band — nearly everything lands
between 0.78 and 0.90. So the *gap* between candidates matters more than the
absolute value, and three results within 0.04 of each other is a case where the
model is not actually discriminating.

Today, all three cross the bar and the top one wins. What that case *should*
trigger is disambiguation — ask the person which they meant. We have the
disambiguation screen; the margin-based rule that routes to it is not
implemented. That is a fair hit.

---

# Round 2 — Speech and Multilingual AI

### Q11. Why Whisper?

Three reasons. It is **MIT-licensed**, so the whole pipeline stays open-source
and a government deployment is not hostage to one vendor's pricing. It handles
**code-switching** natively, which matters enormously — people say "bike repair
பண்ணுவேன்" in one breath. And the same weights run locally on a district machine
or hosted on a GPU, so the deployment can move without the model changing.

We did evaluate a proprietary Indic API and it was better on Tamil. We chose
portability and zero marginal cost, and we are open that this cost us accuracy.

### Q12. "வெல்டிங்" → "வெள்ளி". Then your whole pipeline can be wrong. Why trust it?

You are right, and it is the most serious limitation we have. Whisper misheard
welding as silver, and extraction then faithfully reported *silver work* —
correctly grounded in a transcript that was itself wrong. Evidence verification
cannot catch that, because the quote genuinely is in the transcript.

Three things I would say in defence.

**First, we found it ourselves** — it is in our own documentation with the
measurements. We tested `medium` and `large-v3`, locally and hosted, and the
error persists, so it is the model family rather than our deployment.

**Second, it is language-specific.** Hindi and English transcribe accurately in
our tests. This is a Tamil loanword problem, not a pipeline problem.

**Third, the architecture already assumes it.** Nothing goes from transcript to
match unseen. `/understanding` shows every extracted skill with the words behind
it and lets the person delete it. A mistranscription becomes a card the user
removes in two seconds, not a silent wrong recommendation.

The failure mode we designed against is *the machine asserting something the
person did not say*. This is the machine mishearing — and the human review step
is exactly what catches it.

### Q13. How would you improve Tamil recognition technically?

Four concrete things, in order.

1. **Swap the model for Tamil specifically.** AI4Bharat's IndicWav2Vec is
   Apache-2.0 and trained on Indic speech rather than treating it as a long tail.
   Route by language: Whisper for Hindi and English, IndicWav2Vec for Tamil.
2. **Constrained decoding over the taxonomy.** We know the 44 skills we care
   about. Biasing the decoder toward that vocabulary — a hotword list or a
   shallow-fusion LM — makes "வெல்டிங்" far likelier than "வெள்ளி", because one
   is in the domain vocabulary and one is not.
3. **Phonetic fallback in normalisation.** Match the transcript against taxonomy
   aliases by Tamil phonetic distance, not just embeddings. "வெள்ளி" and
   "வெல்டிங்" are one character apart; edit distance over a phonetic
   transliteration would catch it where cosine similarity does not.
4. **Fine-tune on Common Voice Tamil**, which is CC0 — legally the cleanest
   corpus available for this.

Note that 2 and 3 need no new model at all. They exploit something we already
have: a closed, known vocabulary.

### Q14. "எனக்கு bike repair தெரியும், but welding கொஞ்சம் தான் தெரியும்."

- **Audio → transcript.** Whisper transcribes without translating. The English
  words stay English, the Tamil stays Tamil — the transcript preserves the
  code-mixing exactly as spoken.
- **Transcript → skills.** The LLM extracts two, each with its verbatim
  evidence: *"bike repair தெரியும்"* and *"welding கொஞ்சம் தான் தெரியும்"*. The
  hedge "கொஞ்சம்" (only a little) is recorded as an uncertainty flag rather than
  being smoothed away.
- **Skills → taxonomy.** Each normalises independently. Bike repair lands
  confidently. Welding also matches, but the uncertainty flag travels with it.
- **Confidence → UI.** The welding card appears flagged on `/understanding`. If
  it falls below 0.82 it routes to disambiguation, where **"leave it out" is a
  real answer**.

Our earlier live test did exactly this — flagged welding as uncertain because the
person said "கொஞ்சம்".

### Q15. How do you support code-switching?

By never translating first. That is the whole answer, and it is a deliberate
architectural rule.

Whisper transcribes in the source language. Extraction runs on that mixed
transcript. Evidence phrases are stored in the original mixed form. Only at the
normalisation step do we cross languages — and there we cross into a *vector
space*, not into English text.

The alternative — translate to English, then process — would throw away exactly
the detail this platform exists to handle. We use `saarika`-style transcription
rather than translation models for precisely this reason.

---

# Round 3 — Security and Privacy

### Q16. Why send transcripts to Groq? Isn't that a privacy problem?

It is a real trade and I will not pretend otherwise.

What goes to Groq is **transcript text only** — never audio, never a name, never
a phone number, never anything that identifies the person. We collect no
identity: there is no login, no email, no phone field.

What stays local: text-to-speech runs in our own container via Piper. Embeddings
run against a stateless inference endpoint.

And it is switchable. `LLM_PROVIDER` is a config value with an offline
implementation behind it, and the same open weights can run on a district
machine. For a real government deployment I would expect the model to be
self-hosted — the architecture already supports it, and `/health` would report
it.

### Q17. What happens to raw audio?

It is transcribed and dropped. It is never written to disk or object storage
unless the person explicitly opts in.

And that is not enforced by our code remembering to — it is enforced by the
database:

```sql
constraint sessions_audio_url_requires_optin check (
  audio_retained or audio_url is null
)
```

A row that carries an audio URL without consent **cannot be inserted**. Postgres
rejects it. There is also a `purge_expired_audio()` function for opted-in clips
past the retention window.

### Q18. If someone finds your API endpoint, can they reach your database?

No. **The browser never connects to Postgres.** There is no Supabase client in
the frontend and no database credential in the bundle — I would show you the
built JavaScript. The connection string lives only in the backend's environment.

What they can reach is the API, which is why it has rate limiting, and why every
`/api/admin/*` route re-checks authorisation server-side against a hashed token
rather than trusting anything the client sends.

### Q19. What does RLS protect, and why still need backend authorisation?

RLS is **containment for a leaked key, not the primary control.** If a Supabase
anon key ever escaped, RLS ensures the catalogue tables are public-read and every
personal-data table is unreachable with that key.

But RLS cannot express our actual rules. It cannot know that this session
belongs to the person currently holding the browser tab, or that an admin token
hashes to an active row. That logic lives in the API, which is the real access
control. RLS is the second lock on a door that should never be reached.

### Q20. Rate limiter is per-process. What happens with 10 instances?

The effective limit multiplies by ten — 12 speech requests per minute becomes
120. It is a known limitation and it is documented as one.

The fix is standard: move the counter to Redis so all instances share it, or
push rate limiting to the edge. Neither is hard; both were out of scope for a
single-instance deployment, and shipping a distributed rate limiter we could not
test under load would have been worse than shipping a documented single-instance
one.

---

# Round 4 — Scalability

### Q21. Whisper on CPU — what happens with 1,000 simultaneous uploads?

The premise was true a day ago and we changed it, for exactly this reason.

Local CPU Whisper measured **32.5 seconds** on a 5.8-second clip — 5.6× slower
than realtime. A thirty-second answer would have taken three minutes. That does
not survive ten concurrent users, let alone a thousand.

Transcription now runs on Groq's hardware: the same open weights, **1.4 seconds**
for the same clip. Scaling concurrency is their problem, and the local path
remains in the code for an air-gapped deployment.

At a thousand concurrent, the real bottleneck moves to the provider's rate
limit, which is Q22 and Q23.

### Q22. Synchronous or asynchronous at scale? Design it.

Synchronous today, because a two-second round trip does not justify the
complexity. At scale it has to become asynchronous:

```
User ──► API ──► Queue ──► Worker pool ──► Postgres
  ▲                             │
  └───── WebSocket / SSE ───────┘
```

The API accepts the upload, writes a `sessions` row as *pending*, enqueues a
job, and returns a session id immediately. Workers pull from the queue, call the
speech and LLM providers, and write results back. The client already has a
session id, so it subscribes for progress.

Two things this buys beyond throughput: a provider outage becomes a retry rather
than a failed request, and the queue depth is a scaling signal.

The frontend change is small, because it already handles a slow first response —
we added retry with backoff for cold starts.

### Q23. One LLM provider. What if it goes down, rate-limits, disappears, or gets expensive?

The provider is already an abstraction, not an assumption. `services/llm.py`
supports Groq, Gemini and an offline path behind one interface, selected by an
environment variable. We have swapped it under load once already — we ran on a
different provider yesterday and migrated in a single config change.

- **Goes down** → fall back to the next configured provider; `/health` reports
  which one is live.
- **Rate limited** → the queue from Q22 absorbs the burst.
- **Model disappears** → this happened to us. A pinned model was retired
  mid-build. We now list the provider's available models and re-pick, and the
  config comments say to do exactly that.
- **Cost rises** → the models are open-weight. Qwen and Whisper can be
  self-hosted. That is the strongest argument for choosing open weights over a
  proprietary API: the exit is real.

### Q24. How would you connect to real government data?

`data.gov.in` publishes district-level skilling and scheme catalogues under
**GODL-India**, which permits reuse with attribution. NCS and the state skill
missions publish vacancy data.

Mechanically, little changes: our `opportunities` table already has the shape —
title, organisation, district, type, minimum experience, certifications, NSQF
level, `source_reference`. An ingest job maps their schema to ours, embeds the
required skills, and upserts on `source_reference`.

Being straight with you: our 16 rows are seed data for Salem and Erode. Wiring a
real feed is a day of work, not a research problem — but it is not done.

### Q25. How do you prevent stale opportunities?

Today, badly — `is_active` is a boolean an admin sets. For a real deployment:

- **Ingest on a schedule**, and treat absence from a feed as a closure signal
  rather than waiting for someone to notice.
- **`valid_until`** on the row, so an opportunity expires by default instead of
  living forever.
- **Never promise on our side.** The card shows a scheme reference to quote at
  the office; we do not claim the position is open. That framing already limits
  the damage a stale row can do.

The last point matters most: a stale listing that says "quote reference
OGD/TN/SLM/AUTO/2024/0117" wastes a trip. One that says "you have been matched
to this job" breaks trust.

---

# Round 5 — Government / PM-AJAY Relevance

### Q26. Why is this specifically useful for PM-AJAY beneficiaries? Why not a generic AI job portal?

A job portal starts with a form and a resume. Our users often have neither — the
skills exist, but no document records them, and the form is in a language and a
literacy register they cannot use.

Four things make this specific rather than generic.

**It starts from speech in the person's own language**, including code-mixed
speech, so no writing and no English are required at any point.

**It maps informal work onto NSQF-aligned taxonomy codes.** "என் மாமா கடையில
வேலை" becomes a standard skill id that a scheme can actually act on. That
translation — undocumented experience to formal vocabulary — is the specific
problem PM-AJAY skilling faces.

**It shows its evidence.** For a scheme with entitlement implications, a
recommendation that cannot be traced back to what the person said is not usable.

**It never promises eligibility.** A generic portal optimises for engagement. A
scheme tool has to be honest when the answer is no.

### Q27. How do you onboard someone with no smartphone experience, no English, no resume?

The onboarding *is* the interface: one large microphone button, and the
instruction spoken in their language. There is no form, no signup, no password,
no typing. First screen to first result is one press and one sentence.

Every screen speaks. Text-to-speech is not an accessibility afterthought — it
runs on the results too, so the flow works for someone who cannot read the
output at all.

Realistically it is assisted onboarding: a CSC operator or a scheme facilitator
sits with the person the first time. Our design target is that the *facilitator*
needs no training either.

The resume question answers itself — the transcript becomes the record. That is
the point of the Skill Passport.

### Q28. No certificate — how do you respond without false promises?

We tested this exact question in Tamil: *"எனக்கு சான்றிதழ் இல்லை. பிரச்சனையா?"*

The assistant answers from the stored fields for that one opportunity and
nothing else. If the row requires a certificate the person does not have, it
says so plainly. It does not soften it, and it does not invent a workaround.

This is structural. The assistant is handed the opportunity in front of the
user, their profile, and the match connecting them — not the catalogue, not the
taxonomy. It cannot promise eligibility because it does not have the information
to invent one. And `tests/test_explanation.py` asserts that explanations make no
eligibility promises the data does not support.

One of our real generated bullets warns that a tailoring role expects sewing
experience the person does not have. It talks the user *out* of a match.

### Q29. How would you verify an opportunity is legitimate?

Today we do not — the catalogue is seeded and trusted, which is fine for seed
data and not fine for production.

For a real deployment: opportunities come from **authenticated scheme sources**
(data.gov.in, NCS, state skill missions), each row keeps its `source_reference`
so it is traceable to a government record, and anything submitted directly by an
employer stays unpublished until an administrator approves it. `is_active`
already gates visibility.

The `source_reference` field exists precisely so a claim is checkable at the
office rather than taken on our word.

### Q30. Who is the customer? Who pays?

**Government pays and operates. The beneficiary is the user. Everyone else
benefits.**

Specifically: a state skill mission or the PM-AJAY implementing agency runs it,
because they already hold the opportunity data and the mandate to place people.
Training providers and employers get better-matched candidates without paying,
because charging them would corrupt the ranking — the moment an employer pays
for placement, the deterministic score stops being neutral.

That is a design consequence, not just a business preference. Our whole
transparency claim depends on nobody being able to buy a rank.

---

# Round 6 — Business / Impact

### Q31. Measurable KPIs.

**Funnel:**
- % of sessions producing ≥1 skill above the 0.82 threshold *(extraction yield)*
- % of sessions producing ≥1 match above a usable score *(match yield)*
- % of extracted skills the user edits or deletes *(our error rate, self-reported by users)*

**Quality:**
- Disambiguation rate — how often the system asks instead of guessing
- % of matches where the user opens the detail page *(relevance proxy)*

**Outcome:**
- Days from session to application *(currently unmeasurable — see Q32)*
- Placement rate per 100 sessions
- % of placements where the matched skill was one the person *described* rather
  than *named* — our specific value over a keyword search

**Access:**
- % of sessions in a language other than English *(who we actually reach)*
- % completing without assistance

The one I would hold ourselves to: **skill-edit rate**. If people constantly
correct us, extraction is not working, and it is the only quality metric users
give us for free.

### Q32. How would you measure real employment outcomes?

Honestly: not from our own data, and I would be suspicious of any team claiming
otherwise. We see a session and a match. We do not see whether anyone got hired.

Three ways to close that loop:

1. **Scheme-side reconciliation.** The implementing agency already tracks
   placements. Our `source_reference` is the join key — match this session's
   reference against their placement register.
2. **Follow-up call**, which fits the product: an IVR callback at 30 days asking
   one question in the person's language.
3. **Control comparison.** Compare placement rates for beneficiaries who used
   VoicePath against those who went through the standard counselling flow in the
   same district and period. Without a control, any number we report is
   meaningless.

### Q33. Unit economics at 1 lakh users.

Per session: one transcription (~10s of audio), one extraction call, and up to
eight explanation calls.

Today all of it runs on **free tiers** — Groq for speech and LLM, Supabase for
Postgres, Render and Vercel for hosting. Current marginal cost is genuinely
₹0, which is why we could deploy it as students.

At 1 lakh sessions that stops being free, so the honest projection: roughly
5,000–10,000 LLM tokens per session, plus transcription. At commodity rates that
lands in the range of a few rupees per session — call it low single-digit lakhs
of rupees for 1 lakh sessions, dominated by explanation generation.

Two levers that change the number sharply. **Explanations are the bulk of the
cost** and could be templated for the common cases — our offline path already
does this. And **self-hosting** an open-weight model converts a per-call cost
into a fixed one, which for a government deployment at that volume is almost
certainly cheaper.

I would rather give you the shape and the levers than a precise figure I cannot
defend.

### Q34. Why would government adopt this instead of building it internally?

They might build it, and that would be a good outcome — it is open-source and
the architecture is documented for exactly that reason.

What we offer is that the hard parts are already decided and tested: the
evidence-verification rule, the deterministic ranking, the multilingual taxonomy
mapping, the honest degradation. Those are the design decisions that take months
to get right and are easy to get wrong, and the wrong versions are hard to
detect until someone is harmed by them.

The realistic answer is not "adopt instead of building" — it is that this is a
working reference implementation of the difficult parts, with 178 tests
asserting the guarantees.

### Q35. Biggest barrier to real-world deployment? Be honest.

**Data, not technology.**

We have 16 seeded opportunities. The system is only as useful as the catalogue
behind it, and getting live, accurate, current opportunity data out of state
skill missions and into one schema is an institutional problem — data-sharing
agreements, inconsistent formats, update cadences nobody controls. No amount of
engineering solves it.

Second, and specific to us: **Tamil transcription accuracy**. We are deploying
into Tamil Nadu with the language our pipeline handles least well. That has a
known fix and we have not shipped it.

Third: this needs assisted onboarding at first, which means CSC operator time —
a real operational cost, not a technical one.

---

# Round 7 — Testing and Reliability

### Q36. 178 tests — what are you actually testing? Why isn't "API returns 200" enough?

Because 200 means the pipeline ran, not that it was correct or safe. Our tests
assert the **guarantees**, since those are what would harm someone if they broke:

- `test_extraction.py` — evidence grounding in all three languages, and that
  invented skills are rejected
- `test_matching.py` — weights, determinism, each score component, tie-breaking
- `test_explanation.py` — that explanations cannot re-rank, make no eligibility
  promises, and use no jargon
- `test_normalization.py` — alias matching across scripts, no silent upgrades
- `test_places.py` — Tamil, Hindi and English place names, including case endings
- `test_localization.py` — every skill has Tamil and Hindi labels
- `test_catalogue_sync.py` — the SQL and Python catalogues cannot drift apart
- `test_api.py` — the full pipeline, privacy invariants, the admin gate

The whole suite runs **offline** — no keys, no network, no database — in about
1.5 seconds. Deliberate: these guarantees are properties of our code, and a test
that needed a vendor to demonstrate them would be testing the wrong thing.

### Q37. How do you test a non-deterministic model?

By testing the **properties** the output must satisfy, never the output text.

We never assert "the model returns X". We assert that whatever it returns is
grounded — that every `evidence_phrase` appears verbatim in the transcript. That
holds for any model, any temperature, any wording.

And where determinism actually matters, we removed the model. `matching.py` has
no LLM in it, so ranking is exactly testable. That was an architectural choice
made partly *for* testability.

### Q38. How do you test hallucination prevention?

Directly: feed the validator a model response quoting text that is not in the
transcript, and assert the skill is dropped. That is a unit test over
`_validate`, and it is deterministic because the validator is just string
search.

We also test the harder direction — a skill that *is* real and correctly quoted
survives — because a validator that drops everything would trivially pass the
first test.

### Q39. How do you test multilingual support?

Three ways. Extraction grounding is tested with Tamil, Hindi and English
transcripts. `test_places.py` covers place names across scripts, including Tamil
case endings — a real bug we found where "சேலத்துல" scored 0.20 against a Salem
job. And `test_localization.py` asserts every one of the 44 taxonomy skills has
Tamil and Hindi labels, so an English skill name can never leak into a Tamil
sentence.

That last test exists because it happened.

### Q40. You replace Qwen with another LLM tomorrow. How do you know nothing broke?

The suite runs offline against the deterministic providers, so it verifies the
plumbing but not the new model's behaviour. For the model itself:

The property tests carry over unchanged — grounding, no re-ranking, no
eligibility promises are all model-agnostic assertions.

What we would add for a swap is a small **golden-transcript set**: fifteen or
twenty real transcripts across the three languages, with the skills a human says
should be extracted. Run the new model, measure recall and precision against
that set, compare to the incumbent. We did this informally when choosing Qwen —
it was the only candidate of three to extract "diagnosing engine problems by
sound" from a Tamil transcript — but it is not automated, and it should be.

---

# Round 8 — Adversarial

### Q41. "Your AI says I'm a mechanic. What if I'm lying?"

We do not verify, and we do not claim to. VoicePath records what a person said
about themselves and matches it — it is a structured interview, not a
credentialing system.

Two things limit the harm. The output is a **claim with its evidence attached**,
not a certification: the passport shows the words the person used, so anyone
reading it knows the source. And verification already exists downstream — the
employer or training provider assesses the candidate, exactly as they would for
any applicant.

What we do refuse is *inflating* the claim. We will not turn "I helped at my
uncle's shop" into "3 years professional experience". The person can lie; the
system will not lie on their behalf.

### Q42. "What stops someone claiming 10 years when they have none?"

Nothing stops them, and nothing in a self-reported system could.

But notice the effect. Experience is 0.25 of the score, and the match points to
a real opportunity with a real employer who will assess them. Lying gets you an
interview you fail, not a placement.

The design question is whether the *system* amplifies the lie, and it does not:
`experience_years` is null unless a number was actually stated, we record "a few
years" as the person's words rather than rounding it to 3, and every claim
carries its evidence phrase for anyone reading the passport.

### Q43. "100% match — isn't that misleading?"

Fair criticism, and the honest answer is that the number is a **weighted sum of
four components, each in [0,1]** — not a probability of getting the job.

Two things we do right: the breakdown is always visible, so 100% resolves to
four component bars you can inspect. And the PRD explicitly forbids showing a
raw match vector score as a headline number — the bars carry the meaning.

Where I think you have a point: percent framing invites "100% means certain".
"Strong match on all four factors" would be more honest than "100%", and that is
a change I would make.

### Q44. "What if the nearest opportunity isn't the best one?"

Location is deliberately the **smallest weight — 0.10**. Skill match is five
times more important. So a distant job that fits the person's skills outranks a
nearby one that does not, by construction.

We also do not hide the alternatives: the ranked list shows up to eight with
their reasons, so a person can choose a lower-ranked, better-paid, further job.
The system ranks; it does not decide.

What we cannot weigh is what we never collect — willingness to relocate, family
constraints, transport cost. Those are real, and the honest answer is that the
person holds that information and the interface leaves the choice with them.

### Q45. "What if your algorithm discriminates against rural users?"

The specific mechanism to worry about is location scoring, so let me be precise
about it.

We score by **district**, not by distance from a city, and we resolve towns to
districts — someone in Attur is *near* Salem, not far from everywhere. Before we
built that map, rural users were penalised exactly as you describe, and it showed
up as someone in Attur scoring as far from Salem as someone in Kolkata. We
found it and fixed it.

Structurally, our defence is that the ranking is auditable. If someone alleges
rural bias, the score decomposes into four numbers and you can check it. With an
LLM ranking there would be nothing to inspect.

The residual risk is not in the algorithm but in the **catalogue**: if fewer
opportunities are listed in rural districts, rural users get worse results no
matter how fair the maths is. That is a data-coverage problem, and it is the one
I would actually watch.

### Q46. "What if there are no suitable opportunities?"

It does not just say "no jobs found."

The screen says, in the person's language, that nothing here fits their work
*yet*, and invites them to say more — because the most common cause is thin
extraction, not an empty catalogue. From there they can add a skill they did not
mention, or browse the full catalogue rather than only ranked matches.

They also keep the Skill Passport — their skills, in their words, with the
evidence, in a formal vocabulary. That is a durable artefact they can take to a
CSC or an employer even when we have nothing to offer today.

The honest framing: an empty result is usually information about our catalogue,
not about the person. The interface should not make it feel like a judgement on
them.

---

# Round 9 — Future Vision

### Q47. Six months, three highest priorities.

**1. Tamil speech accuracy.** IndicWav2Vec for Tamil, plus taxonomy-constrained
decoding and a phonetic fallback in normalisation. Our worst failure is in our
primary deployment language.

**2. Real opportunity data at district scale.** Automated ingest from
data.gov.in and state skill missions with expiry handling. The system is only as
good as its catalogue, and 16 rows is not a catalogue.

**3. Close the outcome loop.** Scheme-side reconciliation plus IVR follow-up, so
we can say whether anyone actually got work. Without it we are guessing about
our own impact.

Everything else — RAG over scheme documents, richer NER, proficiency levels — is
below these three.

### Q48. Funded deployment architecture — what changes?

```
Users ──► CDN / API gateway ──► API (stateless, autoscaled)
                                     │
                          ┌──────────┴──────────┐
                          ▼                     ▼
                    Queue + workers        Postgres + pgvector
                          │                  (read replicas)
              ┌───────────┼───────────┐
              ▼           ▼           ▼
        Self-hosted   Self-hosted   Piper
          ASR           LLM          TTS
```

Four changes.

**Self-host the models.** At scale, open weights convert a per-call cost into a
fixed one, and a government deployment should not depend on a foreign API for
citizen data. The architecture already supports it — `/health` reports whichever
is live.

**Queue the speech and LLM work**, so a provider hiccup is a retry rather than a
failed request, and queue depth becomes the scaling signal.

**Redis-backed rate limiting**, which fixes the per-process limitation directly.

**Read replicas for matching**, since it is read-heavy and the vector search
dominates.

What deliberately does *not* change: matching stays deterministic and in-process.
It is fast, it is auditable, and distributing it would buy nothing.

### Q49. Could it become a voice-based employment assistant?

Yes, and the pieces are mostly there — we already do speech in, speech out,
grounded Q&A, and a persistent profile.

What we would add, in order: **application tracking**, so it remembers what you
applied for and follows up; **RAG over scheme documents**, so it can answer
"am I eligible under this scheme?" from actual policy text rather than a job
row; **an IVR channel**, so it works on a feature phone with no app at all —
which for our users may matter more than everything else combined; and
**longitudinal skill tracking**, so completing a training course updates the
passport and re-runs matching.

The constraint I would keep: it stays an assistant that shows its evidence, not
an oracle. Every added capability has to survive the same test — can the person
see why it said that?

### Q50. Sixty seconds. Why should your team win?

> Most people here built something that gives an answer.
>
> We built something that shows its working.
>
> A woman in Salem describes fixing her uncle's motorbike, in Tamil, in her own
> words. We turn that into a formal skill record — and next to every line, the
> exact words she said. She can correct us. She can delete it. Nothing goes
> forward that she has not seen.
>
> Then we rank the opportunities with arithmetic. Not a model's opinion —
> arithmetic, the same every time, that you can check. Because when a government
> decides who hears about which livelihood, "the AI said so" is not an answer
> anyone should accept.
>
> We know where it breaks. Our Tamil transcription mishears English loanwords —
> we found it, measured it, and we can tell you exactly how we will fix it.
>
> We are not asking you to trust our system. We built it so you would not have
> to.
