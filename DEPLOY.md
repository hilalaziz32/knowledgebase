# Deploy to Railway (Docker)

The whole system runs as **one container**: the Next.js frontend serves the UI and
spawns the Python agents in-process. Supabase, Gemini, and Airtable are external.

## 1. Create the service
On Railway: New Project → Deploy from GitHub repo → pick this repo. Railway detects
the `Dockerfile` (and `railway.json`) and builds it.

## 2. Set environment variables (Railway → Variables)
These are NOT in the repo (they're gitignored). Add them in Railway:

| Variable | Value |
|---|---|
| `SUPABASE_DB_URL` | `postgresql://postgres.<project>:<password>@aws-1-<region>.pooler.supabase.com:5432/postgres` |
| `GEMINI_API_KEY` | your Gemini key |
| `AIRTABLE_API_KEY` | your Airtable PAT (`pat...`) |
| `AIRTABLE_BASE_ID` | `appP3VJXaEqNopR1l` |
| `GEMINI_LLM_MODEL` | `gemini-2.5-flash` (optional) |
| `GEMINI_EMBED_MODEL` | `gemini-embedding-001` (optional) |

The container already sets `AGENTS_DIR=/app/agents` and `PYTHON_BIN=/app/agents/.venv/bin/python`.
The spawned Python inherits the Railway variables (no `.env` file needed in the image).

> Note on `SUPABASE_DB_URL`: in Railway's plain variable box do NOT escape the `$$`
> in the password (that escaping was only for Next's local `.env.local` loader).

## 3. Networking
Railway sets `$PORT`; the start command binds to it on `0.0.0.0`. Add a public domain
in Railway's settings.

## Local build test
```bash
docker build -t evergreen .
docker run -p 3000:3000 \
  -e SUPABASE_DB_URL=... -e GEMINI_API_KEY=... \
  -e AIRTABLE_API_KEY=... -e AIRTABLE_BASE_ID=appP3VJXaEqNopR1l \
  evergreen
```

## Not deployed / excluded from git
- `chambermedia/`, `agents/clients/` — client transcripts & uploads (confidential)
- all `.env` / `.env.local` — secrets
- `.venv`, `node_modules`, `.next` — build artifacts (rebuilt in the image)

## ⚠️ Security
- The pushed repo contains code only — no keys, no client data.
- This app talks straight to the DB and runs shell commands; keep the deployment
  behind auth (Railway private networking or an auth proxy) — don't expose it open.
- If the old `.env.example` files (with the real password) were ever pushed before
  this scrub, **rotate the Supabase password + Airtable token**, since git keeps history.
