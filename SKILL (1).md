---
name: data-feeder
description: "Feeds Scaletopia's Evergreen Supabase memory and reads it back. Use whenever something needs to go into the evergreen DB or come out of it: ingesting a call transcript, loading clean master-sheet data (client, case studies, pains), saving a finished SMS copy plus its components, saving a direction sheet, refreshing embeddings, synthesizing a niche, or searching the memory for winners, pains, or case studies. Triggers on 'feed the data', 'ingest this transcript', 'load master data', 'save this copy to evergreen', 'embed the new rows', 'synthesize the [niche] niche', 'search evergreen', 'data feeder'. Always run the scripts. Never hand-write SQL."
---

# Data Feeder — Evergreen's intake and retrieval

This skill is the only thing that writes to and reads from the Evergreen DB. The AI does the thinking, the scripts do the storing and finding. You send plain inputs and clean data, the scripts handle chunking, embedding, dedup, and SQL.

## The golden rule

Deterministic work goes through the scripts. Judgment work stays with the AI (and with sister skills like the master-data processor). Even though Supabase MCP can run SQL directly, do not hand-write inserts or embeddings here. The scripts are the one path so embeddings never drift and dedup never breaks. MCP is only for the loose jobs: linking a copy to a campaign by name, and dropping campaign angle info in by hand.

Campaigns and copy_metrics are NOT this skill's job. They are mirrored from Airtable by n8n. This skill never creates a campaign.

## Setup (once)

Copy `.env.example` to `.env` and fill `SUPABASE_DB_URL` and `GEMINI_API_KEY`. Then `pip install -r requirements.txt`. Run every script from the data-feeder root.

## The tasks

For each one: when it runs, the command, and what it does. Pick the matching task, run the script, then run embed.

### 1. Ingest a transcript
When the AI is handed a raw call transcript.
```
python scripts/ingest_transcript.py --client "Big Leap" --source-call-id "fathom_8842" --file call.txt --title "Discovery" --date 2026-06-10
```
Resolves the client, upserts the call on its source id, chunks the transcript turn by turn, inserts the chunks with the niche stamped on, vectors left NULL. Pass `--rechunk` to redo an existing call.

### 2. Load master data
When the master-data-processor skill has produced clean data for a client. That skill reads the messy sheet and the transcripts and emits one JSON file in the shape defined in `references/master-data-contract.md`. This skill does not read xlsx. It only loads clean data.
```
python scripts/load_master_data.py --file big_leap_master.json
```
Validates the payload against the contract, upserts the client row INCLUDING its Airtable record id (this is what lets campaigns link to the client later), upserts case studies on their source_ref, and upserts pains with their confirmed / needs_more flag. A pain already present gets upgraded from needs_more to confirmed, never duplicated. Vectors left NULL. Malformed input is rejected loudly. Read the contract before running so you know the shape.

### 3. Save a copy
When the AI has finished writing SMS copy.
```
python scripts/save_copy.py --file copy.json
```
Inserts the copy with char counts computed, inserts its six components, sets each component verdict to neutral unless the copy is already a winner. campaign_id stays NULL. Linking the copy to its campaign by name happens later through MCP, not here.

### 4. Save a direction sheet (optional)
When the AI wants to log its reasoning for a campaign.
```
python scripts/save_direction_sheet.py --file direction.json
```
Inserts the reasoning row, linked to a campaign by its Airtable id or name if given.

### 5. Refresh embeddings
Run after ANY write above. This is the one embedding path.
```
python scripts/embed.py
```
Walks the registry, finds every row with a NULL vector and non-empty text, embeds it with Gemini, writes it back. Incremental and idempotent, so running it twice is safe and cheap.

### 6. Synthesize a niche
On Friday, or whenever a niche has moved.
```
python scripts/niche_synth.py --niche "DTC ecom / supplements"
```
Gathers every client's pains, call evidence, and winning copy in the niche, clusters out the duplicates, asks the model to write the commonalities, and upserts niche_knowledge. The LLM call is stubbed for Hilal to wire, the gather and cluster steps are done.

### 7. Search the memory
When the AI is writing a brief or copy and needs evidence.
```
python scripts/search.py --type copies --query "supplement founders skeptical of agencies" --niche "DTC ecom" --status winner
```
Types: calls, copies, case_studies, components. Embeds the query, calls the matching RPC, returns JSON. For copies it also returns the real positive_rate so winners can be weighted by results, not guesses.

## Hard rules

- Never hand-write SQL inserts or do embeddings outside `embed.py`.
- Never create a campaign here. Campaigns come from Airtable through n8n.
- Always run `embed.py` after a write, or search will miss the new rows.
- The loader rejects malformed master data on purpose. Fix the upstream emit, do not loosen the loader.
- A client must exist (or be created by the master-data load) before its transcripts, copy, or campaigns can attach to it.

## Pointers

- `references/master-data-contract.md` — the exact shape the master-data-processor must emit and the loader validates.
- `config/embed_registry.json` — which tables and columns get embedded.
- `connections/supabase.py` — the DB connection and client resolution, shared by every script.
