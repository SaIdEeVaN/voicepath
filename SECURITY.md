# Security

VoicePath holds what people say about their work, sometimes their location,
and an admin console that edits the catalogue. This is what protects that, and
how to report a problem.

## Reporting a vulnerability

Please do not open a public issue. Use GitHub's **Security → Report a
vulnerability** on this repository (private vulnerability reporting), or
contact the repository owner directly. Include what you found, how to
reproduce it, and what it exposes. A plea for help typed into the app is
answered with emergency numbers, not with this; if someone is in danger,
call 112.

## What is in place

Reviewed and hardened on 2026-11-04. Each item names where it lives and the
test that holds it.

**Dependencies.** Next.js 16.4.5 (a critical advisory -- remote code execution
through image optimisation -- affected 16.0-16.4.0), FastAPI 0.162 on
Starlette 1.x (eight advisories against 0.41), python-multipart 0.0.33,
pytest 9. `.github/workflows/security-audit.yml` runs `pip-audit` and
`npm audit` every Monday and whenever a dependency file changes, and fails --
emailing the owner -- on any known Python vulnerability or any high or
critical JavaScript one.

**The website** (`frontend/next.config.ts`) sends a Content-Security-Policy
that limits scripts, styles, fonts, images and connections to the site, the
API, the map tiles and Google Fonts; HSTS; `X-Frame-Options: DENY` and
`frame-ancestors 'none'`; `nosniff`; a strict referrer policy; and a
Permissions-Policy that allows the microphone and location to this site only.
The policy is static, so pages stay pre-rendered; it allows inline scripts,
which Next.js needs without per-request nonces. No page renders HTML from data
(`dangerouslySetInnerHTML` is not used; map popups use `textContent`), and
every external link carries `rel="noopener noreferrer"`.

**The API** (`backend/app/security.py`, `tests/test_security.py`):

- Security headers on every response, `Cache-Control: no-store` included --
  sessions hold what a person said about themselves.
- Request bodies capped as they stream in: 256 KB for JSON, the audio limit
  plus form overhead for recordings, so one large request cannot exhaust
  memory. Text fields have length limits in their schemas; uploads must be
  audio.
- CORS admits only the configured frontend origins and the three headers the
  frontend sends.
- Interactive docs (`/docs`, `/openapi.json`) are off on Render and whenever
  `APP_ENV=production`.

**Rate limits** (`services/ratelimit.py`). Three limits per route, all of which
must hold: per session (only a well-formed session id counts), per address
(four sessions' worth), and per route for everyone together (25x) -- the last
is the ceiling that protects the Groq allowance even from a client forging
both its session and its address.

**Admin access** (`routes/admin.py`). Tokens are stored only as SHA-256
hashes; the bootstrap token is compared in constant time and is honoured only
while no admin exists, and never while the database cannot be checked. Ten
wrong tokens from one address in 15 minutes, or a hundred from everywhere,
lock admin routes (429) until the window passes. The API warns at startup if
`ADMIN_BOOTSTRAP_TOKEN` is shorter than 32 characters; make it with
`python -c "import secrets; print(secrets.token_urlsafe(32))"`.

**Pages fetched from search results** (`services/websearch.py`). Only http(s)
on ports 80 and 443, no credentials in the URL, and every address the host
resolves to must be public -- checked again at every redirect, which is
followed by hand. Bodies are read up to 2 MB. Fetched pages wait for an admin's
review before the assistant may cite them.

**Speech and the model.** Raw audio is not kept unless the person opts in, and
the database enforces that with a check constraint. Everything the model
extracts must quote the transcript or it is dropped; matching imports no model
at all; and a model's answer about a scheme must cite a passage from an
approved document or it is refused.

**The database.** Row-level security is on for every table; tables holding
personal data have no policies at all, so a public Supabase key can read none
of them -- only the backend's own connection can. Supabase's security advisor
reports one warning, the `vector` extension living in `public`, which is left
as is: moving it means rewriting the functions that use its types, for little
gain.

**Secrets.** `.env` files are ignored by git; the history was scanned on
2026-11-04 and holds only placeholders. Keys live in Render's and Vercel's
environment settings. GitHub Actions are pinned to commit SHAs; the audit job
is read-only and the offices job may only push its own data file.

## Known limits

- Rate limits are per process. Behind more than one instance they multiply;
  move the counters to Redis before scaling out.
- The address used for limits comes from `X-Forwarded-For` as Render passes
  it, which a client can influence -- hence the global ceiling.
- A session's data is reachable by anyone holding its id. The id is a random
  UUID (122 bits) kept in the tab's sessionStorage and never put in a URL; it
  works like a password for that session, so nothing should log or display it.
