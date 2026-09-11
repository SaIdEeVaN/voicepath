# Database

Supabase Postgres with `pgvector`. Apply the files **in order** — each one assumes the
previous has run.

```bash
psql "$DATABASE_URL" -f db/001_schema.sql
psql "$DATABASE_URL" -f db/002_functions.sql
psql "$DATABASE_URL" -f db/003_seed.sql
psql "$DATABASE_URL" -f db/004_policies.sql
```

Or paste each file into the Supabase SQL editor, in the same order.

Then compute the taxonomy embeddings — semantic normalization does nothing until
`skill_taxonomy.embedding` is populated:

```bash
cd backend
python -m app.scripts.embed_taxonomy
```

## Files

| File | Contents |
|---|---|
| `001_schema.sql` | All tables from PRD §3, plus constraints, indexes and the `updated_at` trigger |
| `002_functions.sql` | `match_skill_taxonomy` (vector search), `scheme_skill_vectors` (N+1 avoidance), `purge_expired_audio` (privacy safety net) |
| `003_seed.sql` | 43 taxonomy skills + 16 Salem/Erode schemes. Idempotent. |
| `004_policies.sql` | RLS. Catalogues are public-read; every personal-data table is unreachable by anon keys. |

## Notes

**Embedding dimension is 768** (`multilingual-e5-base`). If you set `EMBEDDING_MODEL`
to a model with a different output size, change `vector(768)` in `001_schema.sql` and
in both functions in `002_functions.sql`, then re-run `embed_taxonomy`.

**The browser never connects to Postgres.** The FastAPI backend holds `DATABASE_URL`
and is the only database client. RLS is a containment measure for leaked anon keys,
not the primary access control — that is the API.

**Re-running the seed is safe.** `003_seed.sql` uses `on conflict` throughout, so it
updates in place rather than duplicating.

**Audio retention.** `sessions` carries a check constraint that makes `audio_url`
non-null *only* when `audio_retained` is true, so the PRD §7 rule is enforced by the
database and not just by application code. Schedule the purge as a safety net:

```sql
select cron.schedule('purge-audio', '0 3 * * *', $$select purge_expired_audio(90)$$);
```
