# Scaletopia Evergreen — Agents (MVP)

Script-based agents that turn a client's raw material into clean, embedded,
searchable rows in the Evergreen Supabase DB. Gemini does the thinking (parse +
tier + mine), the shared dedup-safe writers do the saving, and one shared embed
path fills every vector. Later these become a FastAPI multi-agent service.

## Setup
```bash
cd agents
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env      # then fill GEMINI_API_KEY, AIRTABLE_API_KEY, AIRTABLE_BASE_ID
```
SUPABASE_DB_URL and the Gemini models are pre-filled in `.env.example`.

## The agents
| Agent | File | Fills | Run when |
|---|---|---|---|
| B — Onboarding | `onboarding_agent.py` | `client_roster` + `master_sheet_pains` | first, client must exist before anything |
| A — Case Study | `case_study_agent.py` | `case_studies` (tiered, dedup on source_ref) | after client exists |
| C — Transcript | `transcript_agent.py` | `client_calls` + `call_chunks` + mined `master_sheet_pains` | per call |
| D — Niche Synth | `niche_synth_agent.py` | `niche_knowledge` | once a niche has enough clients |
| E — Campaign Sync | `campaign_sync_agent.py` | `campaigns` | to mirror Airtable campaigns by client id |

Each agent embeds its own new rows at the end (shared/embed.py), so search never
misses them.

## MVP run order (Kynship)
```bash
cd agents
# 1. client + pains (creates the client)
.venv/bin/python onboarding_agent.py --client "Kynship" --slug kynship \
    --airtable-id recncshNnMmK4OTei \
    --form clients/kynship/onboarding-form.txt \
    --account clients/kynship/account-targeting.csv \
    --persona clients/kynship/persona-targeting.csv

# 2. case studies (tiered)
.venv/bin/python case_study_agent.py --client kynship \
    --file clients/kynship/case-studies.csv \
    --source-label "Kynship Master Sheet · Tab 4"

# 3. transcripts (loop over clients/kynship/transcripts/*.txt)
.venv/bin/python transcript_agent.py --client kynship \
    --source-call-id kynship_call1 --file clients/kynship/transcripts/call1.txt \
    --title "Call 1" --provider manual

# 4. niche synthesis (after enough data)
.venv/bin/python niche_synth_agent.py --niche "DTC ecom"
```

## Design rules (do not break)
- **One embedding model.** Gemini `gemini-embedding-001`, 1536-dim, must match the
  search side. Never embed inside an agent's LLM step — only via shared/embed.py.
- **One write path.** All inserts go through shared/writers.py so dedup keys
  (`source_ref`, `client_slug+text`, `source_call_id`) stay identical to data-feeder.
- **Client first.** A client must be in `client_roster` before calls/cases/copy attach.
- **Naming.** `slug` and `niche` are plain text and link everything. Spell them
  identically everywhere (Airtable, onboarding, niche synth) or links break silently.

## Airtable (campaign sync)

Token: agents read the `AIRTABLE` token from the repo-root `.env` directly (NOT the
MCP server, which uses a separate token). Base: `appP3VJXaEqNopR1l`
(Operations & Data Analytics). Verified this token sees the same bases as MCP.

Relevant Airtable tables: `📂 Clients`, `📢 Campaigns`, `✍️ Copy`,
`📧 Daily Email Stats`, `📱 Daily SMS Stats`, `Relinked Campaigns`.

The campaign Name encodes the strategy and we parse it:
```
"Kynship - Household Goods | 5-200E | USA, CA | V4"
 <client> - <vertical/angle>  | <segment> | <region> | <variant>
```
Mapping into the DB `campaigns` table:
| DB column | From Airtable |
|---|---|
| `airtable_campaign_id` | Airtable record id (dedup key) |
| `airtable_client_id` | the client's record id (`recncshNnMmK4OTei` for Kynship) |
| `name` | Name (full) |
| `client_slug` | resolved from client_roster |
| `niche` | falls back to the client's niche |
| `angle` | parsed vertical, e.g. "Household Goods" |
| `segment` | parsed band, e.g. "5-200E" |
| `channel` | Campaign Type: SMS->sms, EmailBison->email |
| `notes` | region, variant, status, ext id |

Run:
```bash
.venv/bin/python campaign_sync_agent.py --client kynship --dry-run   # preview
.venv/bin/python campaign_sync_agent.py --client kynship             # write
```
The client must exist in client_roster first (needs its `airtable_client_id`).

`copy_metrics` and the `✍️ Copy` body sync are NOT built yet — next step. Copy can
also be saved with the data-feeder `save_copy.py`.
