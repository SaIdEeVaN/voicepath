---
title: VoicePath API
emoji: 🎙️
colorFrom: indigo
colorTo: gray
sdk: docker
app_port: 7860
pinned: false
---

# VoicePath API

Backend for VoicePath — voice-first skill discovery for Scheduled Caste
beneficiaries under the PM-AJAY skilling ecosystem. FastAPI; the frontend is a
separate Next.js app that talks to this over HTTP.

`/docs` for the API surface, `/health` for which providers are actually live.

## What runs where

| Layer | Component | Runs |
|---|---|---|
| Speech-to-text | Whisper large-v3 | Groq |
| Text-to-speech | Piper | In this container |
| Embeddings | `multilingual-e5-base` | In this container |
| Extraction / explanation | `qwen/qwen3.8-27b` | Groq |
| Storage | Postgres + pgvector | Supabase |

Both hosted components are open-weight models; the hosting is what is bought,
not the model. Set `STT_PROVIDER=local` to move transcription into the container
too — it works, but measured 32.5s on a 5.8s clip on a CPU, against 1.4s hosted.

## Configuration

Set these in **Settings → Variables and secrets**, never in the repo. This Space
is public if the visibility says so, and anything committed is readable.

Secrets:

- `DATABASE_URL` — Supabase **pooler** URL. The direct `db.PROJECT.supabase.co`
  host is IPv6-only and will not resolve here. Username is `postgres.PROJECT`,
  and the password must be percent-encoded (`@` → `%40`).
- `LLM_API_KEY` — Groq, from console.groq.com/keys
- `ADMIN_BOOTSTRAP_TOKEN` — guards `/api/admin/*`, and is honoured only while
  the `admin_users` table is empty

Variables:

- `CORS_ORIGINS` — the frontend origin, e.g. `https://your-app.vercel.app`.
  Without a match here every browser request fails in a way that looks exactly
  like a dead backend.

## Notes for the free CPU tier

The embedding model and Piper voices are baked into the image at build time, so
a cold start does not also download 1.1GB. It still has to load the model into
memory — expect the first request after the Space sleeps to take about a minute.

Nothing in `sessions` holds audio unless a user explicitly opted in; the
database enforces that with a check constraint rather than trusting this code.
