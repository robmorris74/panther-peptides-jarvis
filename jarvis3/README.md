# Jarvis 3 clean rebuild

This directory is intentionally independent from the legacy Jarvis runtime.

## Milestone 1 acceptance contract
- `/health` returns 200 without authentication.
- `/ready` explicitly reports whether owner password, OpenAI key, and persistent DB are ready.
- Owner login uses only `JARVIS_OWNER_PASSWORD`; there is no database-password fallback.
- Session secret and SQLite database live on `/app/data`.
- Authenticated text chat uses the OpenAI Responses API.
- The Docker build compiles the actual application; it contains no release-number grep assertions.
- A restart preserves chat history and the session signing secret when `/app/data` is mounted persistently.

## Required environment
`JARVIS_OWNER_PASSWORD`, `OPENAI_API_KEY`

Optional: `JARVIS_MODEL` (default `gpt-5-mini`), `JARVIS_COOKIE_SECURE` (default `1`).

## Deployment
Docker context: repository root
Dockerfile: `jarvis3/Dockerfile`
Persistent disk mount: `/app/data`
Health check: `/health`

Do not point the existing production Jarvis service at this branch. Create a separate staging service first.
