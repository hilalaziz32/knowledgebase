# Scaletopia Evergreen — Frontend

A Next.js (App Router) control panel for the Evergreen memory. Server components
read Supabase directly via `pg`; agent actions run the Python agents in `../agents`
through API routes.

## Run
```bash
cd frontend
npm install
# .env.local is already set (SUPABASE_DB_URL + AGENTS_DIR)
npm run dev          # http://localhost:3000
```
Prereqs: the `../agents` venv must be set up with a working `.env` (Gemini + Airtable
keys), since the API routes shell out to those scripts.

## What it does
- **/** — dashboard: every client with live counts (calls, pains, case studies, campaigns)
- **/clients/new** — onboard a client: paste the form → runs `onboarding_agent.py`
- **/clients/[slug]** — client detail (pains, case studies, calls, campaigns, niche knowledge) plus action tabs:
  - **Add case studies** → `case_study_agent.py` (split, tier S–D, dedup, embed)
  - **Add transcript** → `transcript_agent.py` (chunk, embed, mine pains)
  - **Sync campaigns** → `campaign_sync_agent.py` (from Airtable, dry-run or write)
  - **Synthesize niche** → `niche_synth_agent.py`
- **/clients/[slug]/copy** — write a copy (t1/t2 + 6 components) → `copy_agent.py` (saves + embeds);
  link any copy to a synced campaign via dropdown (`/api/copy/link`, inherits niche/persona; shows PR rate)
- **/search** — semantic search across pains / calls / case studies / copies / components → `search_agent.py`

## How it's wired
```
Browser → Next API route → (read) pg → Supabase
                         → (act)  spawn ../agents/.venv/bin/python <agent>.py → Supabase + Gemini
```
- `lib/db.ts` — shared pg pool (SSL on, for the Supabase pooler)
- `lib/agents.ts` — spawns a python agent, strips warning noise, returns stdout
- Pasted text (form/case studies/transcript) is saved to `agents/clients/_uploads/` then passed with `--file`

## Gotchas
- **`.env.local` password escaping** — the DB password contains `$$`; it's written as
  `\$\$` so Next's env loader doesn't treat it as variable expansion. Keep it escaped.
- Agent actions are synchronous HTTP calls; long transcripts can take a minute. Route
  `maxDuration` is bumped accordingly. (When you move to the FastAPI backend, these become
  async jobs.)
- This is an internal tool: it talks straight to the DB and runs local scripts. Don't expose it publicly as-is.
