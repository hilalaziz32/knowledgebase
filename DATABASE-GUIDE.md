# Evergreen Database — Full Guide (easy English)

This file explains **every table, every field** in the Evergreen Supabase DB.
For each field: what it means, **how it is entered** (which script/source puts it
there), and **how it is used** later.

Two important rules first:

1. **Scripts write, AI thinks.** We never type raw SQL. Each table is filled by a
   specific script (or by n8n from Airtable). The script names are in the
   `data-feeder/scripts/` folder.
2. **Embeddings** (the "meaning vectors" used for smart search) are NEVER written
   by hand. Every embedding column is left empty (`NULL`) when a row is created,
   and one command — `python scripts/embed.py` — fills them all later.

Legend used below:
- 🧠 = embedding column (search-by-meaning)
- 🔁 = this row is deduped (running twice will not make a copy)
- 📥 = how the value gets in
- 🎯 = how the value is used

---

## How the whole thing connects (read this first)

```
client_roster   (the client — the anchor of everything)
   │
   ├── client_aliases      (nicknames that point to this client)
   │
   ├── client_calls        (full raw transcript of each call)
   │       └── call_chunks 🧠   (that transcript cut into small searchable pieces)
   │
   ├── case_studies 🧠      (proof / results stories we can quote)
   │
   ├── master_sheet_pains 🧠 (buyer pains, lingo, dreams, beliefs, objections)
   │
   └── copies 🧠            (the finished SMS messages we wrote)
           └── copy_components 🧠  (each copy broken into its 6 parts)

campaigns        (comes from Airtable via n8n — we never create it)
   ├── copies link to it by campaign_id
   ├── copy_metrics   (real results: sent / replies / booked)  ← from Airtable
   └── direction_sheets (our reasoning notes for the campaign)

niche_knowledge 🧠  (one summary per niche, pooled from ALL clients in that niche)

VIEWS (not real tables, just saved filters):
   winners            = copies where status = winner
   losers             = copies where status = loser
   copy_performance   = copies joined to their metrics, with rates calculated
```

**The golden link:** almost everything connects through two things —
`client_slug` (which client) and `niche` (which industry). These are plain text.
If the spelling is different in two places, the link silently breaks. Keep niche
and slug spelled **exactly the same everywhere.**

---

# CORE TABLES (the data we own and write ourselves)

## 1. `client_roster` — the master list of clients
This is the anchor. Every call, case study, pain, and copy attaches to a client here.

📥 Entered by: `load_master_data.py` (from the clean JSON the master-data-processor makes).
🔁 Deduped on `slug` (re-loading the same client updates it, never duplicates).

| Field | Easy meaning | How entered | How used |
|---|---|---|---|
| `id` | Auto number, the row's own ID | Database makes it automatically | Internal linking |
| `client` | The client's display name, e.g. "Big Leap" | From JSON `client.client` | Shown to humans; used to match by name |
| `slug` | Short safe name, e.g. `big_leap` | From JSON `client.slug` | **The key everything attaches to** |
| `airtable_client_id` | The client's record ID in Airtable, e.g. `recA1B2...` | From JSON `client.airtable_client_id` | **This is how Airtable campaigns find this client.** If empty, campaigns can't link |
| `offer` | What they sell, e.g. "SEO / organic traffic" | From JSON `client.offer` | Context when writing copy |
| `niche` | Their industry, e.g. "legal" | From JSON `client.niche` | Links client to niche_knowledge & filters |
| `sub_niche` | More specific, e.g. "personal-injury law" | From JSON `client.sub_niche` | Finer filtering |
| `signature_case_study_ids` | List of their best case study IDs | Set manually / later | Quick pick of strongest proof |
| `status` | active / paused etc. | Set manually | Filtering live clients |
| `created_at` / `updated_at` | Timestamps | Database fills automatically | Tracking |

**Note:** on re-load, if the new JSON leaves a field empty, the old value is kept
(it uses `coalesce`). So you can't accidentally wipe a good value with a blank one.

---

## 2. `client_aliases` — nicknames for a client
So "Big Leap", "bigleap", "BL" all point to the same `client_slug`.

📥 Entered by: manually / setup (not a main script).
🎯 Used by: `resolve_client()` when ingesting a transcript, so a slightly different
name still finds the right client.

| Field | Easy meaning |
|---|---|
| `id` | Auto number |
| `alias` | The nickname text, e.g. "BL" |
| `client_slug` | The real client it points to |
| `created_at` | Timestamp |

---

## 3. `client_calls` — the full raw transcript of each call
One row per call. Holds the **whole** transcript text.

📥 Entered by: `ingest_transcript.py` (you hand it a transcript file).
🔁 Deduped on `source_call_id` (same call ID won't be ingested twice unless you pass `--rechunk`).

| Field | Easy meaning | How entered | How used |
|---|---|---|---|
| `id` | Auto number | DB | Links to call_chunks |
| `client_slug` | Which client | Resolved from the `--client` you pass | Filtering by client |
| `title` | Call name, e.g. "Discovery" | From `--title` | Human label |
| `call_date` | Date of call | From `--date` | Sorting / context |
| `source` | Where it came from, e.g. "fathom", "manual" | From `--provider` | Tracking origin |
| `source_call_id` | Unique ID of the call, e.g. `fathom_8842` | From `--source-call-id` | **Dedup key** |
| `participants` | Who was on the call | From `--participants` | Context |
| `raw_transcript` | The ENTIRE transcript text | From the file you pass | Re-chunking later if needed |
| `created_at`/`updated_at` | Timestamps | DB | Tracking |

---

## 4. `call_chunks` 🧠 — the transcript cut into small pieces
The script splits the call **speaker turn by speaker turn** (around 400 tokens each,
with small overlap). This is what we actually search.

📥 Entered by: `ingest_transcript.py` automatically (you don't write chunks yourself).
🧠 `embedding` filled later by `embed.py`.

| Field | Easy meaning | How entered | How used |
|---|---|---|---|
| `id` | Auto number | DB | — |
| `call_id` | Which call this piece belongs to | Set by script | Links back to client_calls |
| `client_slug` | Which client | Stamped by script | Filter search by client |
| `niche` | Which industry | Stamped from client's niche | Filter; feeds niche synthesis |
| `chunk_index` | Piece number (0,1,2…) | Set by script in order | Keeps order |
| `chunk_text` | The actual words of that piece | Cut by script | The text that gets embedded & shown |
| `embedding` 🧠 | Meaning vector of the chunk | **Empty at first**, filled by embed.py | Smart search: "find where they talked about X" |
| `created_at`/`updated_at` | Timestamps | DB | — |

---

## 5. `case_studies` 🧠 — proof / results stories
"Brand X grew 3.1x in 7 months." These are the proof lines we put in copy.

📥 Entered by: `load_master_data.py` (from the clean JSON).
🔁 Deduped on `source_ref` (same ref = update in place, no duplicate).

| Field | Easy meaning | How entered | How used |
|---|---|---|---|
| `id` | Auto number | DB | Linked from copies (`case_study_id`) |
| `source_ref` | Where this came from, e.g. "Master Sheet · Tab 4 · row 12" | From JSON | **Dedup key** |
| `owner_client_slug` | Which client owns this proof | From JSON (falls back to client) | Filtering |
| `subject_brand` | The brand the result is about | From JSON (**required**) | The name we quote |
| `niche` / `sub_niche` | Industry | From JSON (falls back to client's) | Filtering / matching |
| `service` | What was done, e.g. "SEO" | From JSON | Context |
| `before_state` | The "before" situation | From JSON | Story setup |
| `after_state` | The "after" win (**required**) | From JSON | The headline result |
| `notable_results` | Extra impressive details | From JSON | Strong proof lines |
| `timeframe` | How long it took, e.g. "7 months" | From JSON | Believability |
| `mechanism_literal` | What was actually done (plain) | From JSON | Explaining how |
| `unique_mechanism` | The clever angle/spin | From JSON | The "secret sauce" line in copy |
| `tier` | Quality grade A–D (default D) | From JSON | Pick best proof first |
| `source_url` | Link to evidence | From JSON | Verify |
| `result_embedding` 🧠 | Meaning of after_state + notable_results | embed.py | Search by result type |
| `unique_mechanism_embedding` 🧠 | Meaning of the unique mechanism | embed.py | Search by angle |
| `niche_embedding` 🧠 | Meaning of niche + sub_niche | embed.py | Match proof to a niche |
| `created_at`/`updated_at` | Timestamps | DB | — |

---

## 6. `master_sheet_pains` 🧠 — voice of the customer
Every pain, the words buyers use (lingo), their dreams, beliefs, and objections.

📥 Entered by: `load_master_data.py`.
🔁 Deduped on `client_slug + exact text`. If a pain was `needs_more` and comes back
as `confirmed`, it gets **upgraded** — never duplicated.

| Field | Easy meaning | How entered | How used |
|---|---|---|---|
| `id` | Auto number | DB | — |
| `client_slug` | Which client | From JSON | Filtering / dedup |
| `niche` / `sub_niche` | Industry | From JSON (falls back to client) | Feeds niche synthesis |
| `kind` | One of: pain, lingo, dream, belief, objection | From JSON (**must be one of these**) | Decides how it's used in copy |
| `persona` | Who feels it, e.g. "managing partner" | From JSON | Target the right person |
| `item_text` | The actual pain/phrase text | From JSON (**required, non-empty**) | The line we embed & quote |
| `confidence` | `confirmed` or `needs_more` | From JSON (default needs_more) | Trust level; upgrades over time |
| `source` | Where it was found, e.g. "call fathom_8842 · chunk 6" | From JSON | Traceability |
| `embedding` 🧠 | Meaning of item_text | embed.py | Search pains by meaning; clustering |
| `created_at`/`updated_at` | Timestamps | DB | — |

**Why confidence matters:** pains are rarely written down cleanly. We save what we're
sure of as `confirmed`, and best guesses as `needs_more`. As more calls come in, the
picture fills in by itself — the same pain re-confirmed gets upgraded.

---

## 7. `copies` 🧠 — the finished SMS messages
The real output: the message we wrote, plus all the strategy tags about it.

📥 Entered by: `save_copy.py` (from a copy JSON file).
Note: `campaign_id` is left empty here; linking copy to its campaign happens **later
by name through MCP**, not in this script. `char_t1`/`char_t2` are **calculated
automatically** (counted from t1/t2).

| Field | Easy meaning | How entered | How used |
|---|---|---|---|
| `id` | Auto number | DB | Links to copy_components |
| `airtable_copy_id` | Its Airtable ID (if any) | From JSON | Cross-reference |
| `origin` | Where it came from (default `scaletopia_send`) | From JSON / default | Tracking |
| `client_slug` | Which client | From JSON | Filtering |
| `campaign_id` | Which campaign (linked later) | **Empty at save**, linked via MCP | Join to results |
| `case_study_id` | Which proof it uses | From JSON | Link copy to its proof |
| `niche` / `sub_niche` | Industry | From JSON | Filtering / matching |
| `persona` | Who it targets | From JSON | Filtering |
| `sophistication` | How aware the market is | From JSON | Angle choice |
| `channel` | sms / email (default sms) | From JSON / default | Filtering |
| `t1` | First text message | From JSON | The actual copy; embedded |
| `t2` | Second/follow-up message | From JSON | The actual copy; embedded |
| `char_t1` | Character count of t1 | **Auto-counted by script** | Keep SMS within limits |
| `char_t2` | Character count of t2 | **Auto-counted by script** | Keep SMS within limits |
| `lever` | The main psychological pull used | From JSON | Learn what works |
| `pattern` | The structure/template | From JSON | Reuse patterns |
| `what_carries` | What makes the message land | From JSON | Notes |
| `proof_framing` | How the proof is presented | From JSON | Notes |
| `unique_mechanism` | The clever angle | From JSON | Embedded; reused |
| `pattern_interrupt` | The scroll-stopper bit | From JSON | Notes |
| `cta` | The call to action | From JSON | Notes |
| `relevance_type` | How it's made relevant | From JSON | Notes |
| `status` | draft / winner / loser / neutral | From JSON (default draft) | Decides winners view & verdicts |
| `model_score` | AI's score of the copy | From JSON | Ranking |
| `why_it_worked` | Reason it won | From JSON | Learning |
| `why_it_failed` | Reason it lost | From JSON | Learning |
| `lineage` | History/parents of this copy (JSON) | From JSON | Track how copy evolved |
| `full_copy_embedding` 🧠 | Meaning of t1 + t2 | embed.py | Search whole copies |
| `t1_embedding` 🧠 | Meaning of t1 | embed.py | Search opening lines |
| `unique_mechanism_embedding` 🧠 | Meaning of the mechanism | embed.py | Search by angle |
| `created_at`/`updated_at` | Timestamps | DB | — |

---

## 8. `copy_components` 🧠 — each copy broken into its 6 parts
Every copy is split into its building blocks, so we can study parts separately.
The 6 types: **disarmer, identity, case_line, unique_mechanism, relevance, cta**.

📥 Entered by: `save_copy.py` (from the `components[]` array in the copy JSON).
The `verdict` is set to `winner` if the whole copy is a winner, otherwise `neutral`.

| Field | Easy meaning | How entered | How used |
|---|---|---|---|
| `id` | Auto number | DB | — |
| `copy_id` | Which copy this part belongs to | Set by script | Links to copies |
| `component_type` | Which of the 6 parts | From JSON | Study parts by type |
| `item_text` | The actual words of that part | From JSON | Embedded & reused |
| `verdict` | winner / neutral | Set by script from copy status | Find winning hooks/CTAs |
| `niche` | Industry | Copied from the copy | Filtering |
| `persona` | Who it targets | Copied from the copy | Filtering |
| `lever` | The pull used | Copied from the copy | Filtering |
| `embedding` 🧠 | Meaning of item_text | embed.py | "Find winning CTAs in legal niche" |
| `created_at`/`updated_at` | Timestamps | DB | — |

---

## 9. `niche_knowledge` 🧠 — the pooled cheat-sheet per niche
ONE row per niche (e.g. "legal"). It combines what **all** clients in that niche
taught us, so a new campaign starts informed.

📥 Entered by: `niche_synth.py` — it gathers all pains/calls/winning-copy in the
niche, groups duplicates, then asks an AI to write the summary.
⚠️ **The AI summary step is not wired yet** (a TODO in the script). Until it's
finished, this table cannot be filled by the script.
🔁 Upsert on `niche` (re-running overwrites the one row, never duplicates).

| Field | Easy meaning | How entered | How used |
|---|---|---|---|
| `id` | Auto number | DB | — |
| `niche` | The industry name | From `--niche` argument | The key (one row per niche) |
| `top_pains` | List of the biggest pains + how many clients have each (JSON) | AI synthesis | Brief a new campaign fast |
| `shared_lingo` | Words real buyers use (JSON list) | AI synthesis | Sound like the buyer |
| `dream_outcomes` | What they really want (JSON list) | AI synthesis | Aim the promise |
| `winning_levers` | Angles that scored, most common first (JSON list) | AI synthesis | Pick proven angles |
| `commonalities_summary` | 2–4 sentence summary | AI synthesis | The headline takeaway; embedded |
| `summary_embedding` 🧠 | Meaning of the summary | embed.py | Search across niches |
| `source_client_slugs` | Which clients fed this (list) | Set by script | Know where it came from |
| `refreshed_at` | When it was last rebuilt | Set by script | Know if it's stale |
| `created_at`/`updated_at` | Timestamps | DB | — |

---

## 10. `direction_sheets` — our reasoning notes for a campaign
"Here is WHY we chose this angle for this campaign." Strategy memory, optional.

📥 Entered by: `save_direction_sheet.py` (from a direction JSON file).
It links to a campaign by `campaign_id`, or by Airtable ID, or by campaign name —
or stays unlinked if none given.

| Field | Easy meaning | How entered | How used |
|---|---|---|---|
| `id` | Auto number | DB | — |
| `campaign_id` | Which campaign | Resolved by script (id/airtable/name) | Tie reasoning to campaign |
| `client_slug` | Which client | From JSON | Filtering |
| `niche` | Industry | From JSON | Filtering |
| `persona` | Who we targeted | From JSON | The plan |
| `lever` | The pull we chose | From JSON | The plan |
| `case_study_id` | The proof we picked | From JSON | The plan |
| `unique_mechanism` | The angle | From JSON | The plan |
| `objection` | The objection we tackled | From JSON | The plan |
| `cta_softness` | How soft/hard the CTA is | From JSON | The plan |
| `why_now` | The urgency reason | From JSON | The plan |
| `hypothesis_line` | Our bet in one sentence | From JSON | Compare against results later |
| `outcome_summary` | What actually happened | From JSON (filled later) | Learning |
| `created_at`/`updated_at` | Timestamps | DB | — |

---

# AIRTABLE-MIRRORED TABLES (n8n fills these — the skill NEVER creates them)

## 11. `campaigns` — the campaigns themselves
These come **from Airtable through n8n**. The data-feeder skill never makes a campaign.

🎯 Used by: copies link to it (`campaign_id`); copy_metrics attach results to it;
its `niche` connects it to `niche_knowledge`.

| Field | Easy meaning | How entered |
|---|---|---|
| `id` | Auto number | DB |
| `airtable_campaign_id` | Its Airtable record ID | From Airtable via n8n |
| `airtable_client_id` | The client's Airtable ID | From Airtable; matched to client_roster |
| `name` | Campaign name | From Airtable |
| `client_slug` | Which client | Resolved from airtable_client_id |
| `niche` | Industry | From Airtable — **this links to niche_knowledge** |
| `persona` | Who it targets | From Airtable |
| `segment` | The list segment | From Airtable |
| `angle` | The campaign angle | From Airtable (or added by hand via MCP) |
| `channel` | sms / email | From Airtable |
| `list_source` | Where the list came from | From Airtable |
| `start_date` | When it started | From Airtable |
| `notes` | Free notes | From Airtable |
| `created_at`/`updated_at` | Timestamps | DB |

---

## 12. `copy_metrics` — the real-world results
The actual numbers: how many sent, how many replied positively, how many booked.

📥 Entered by: n8n from Airtable.
🎯 Used by: the `copy_performance` view to calculate rates.

| Field | Easy meaning |
|---|---|
| `id` | Auto number |
| `airtable_metric_id` | Its Airtable ID |
| `airtable_copy_id` | Which copy (Airtable side) |
| `airtable_campaign_id` | Which campaign (Airtable side) |
| `copy_id` | Which copy (our DB) |
| `campaign_id` | Which campaign (our DB) |
| `period_start` / `period_end` | The date range these numbers cover |
| `region` | Which region |
| `sent` | How many messages sent |
| `positive_responses` | How many replied positively |
| `booked_calls` | How many calls booked |
| `created_at`/`updated_at` | Timestamps |

---

# VIEWS (not real tables — just saved, live filters)

A view stores no data of its own. It is a saved query that always shows fresh results.

## 13. `winners` (VIEW)
Just the rows from `copies` where `status = 'winner'`. Same columns as `copies`.
🎯 Used to quickly pull only the copy that worked.

## 14. `losers` (VIEW)
Just the rows from `copies` where `status = 'loser'`. Same columns as `copies`.
🎯 Used to study what failed and avoid repeating it.

## 15. `copy_performance` (VIEW)
Joins `copies` to `copy_metrics` and **calculates the rates for you**.

| Field | Easy meaning |
|---|---|
| `copy_id` | Which copy |
| `niche` / `persona` / `lever` | Tags carried from the copy |
| `status` | winner / loser / etc. |
| `sent` | Total sent |
| `positives` | Total positive replies |
| `booked` | Total booked calls |
| `positive_rate` | positives ÷ sent (the real win rate) |
| `sent_per_positive` | How many sends to get one positive |
| `sent_per_booked` | How many sends to get one booking |

🎯 This is how "winner" is judged by **real results**, not just by guess. When
searching copies, this view gives the true positive_rate so good copy is weighted
by what actually happened.

---

# THE TWO TABLES WE IGNORE
`companies` and `people` — not part of this evergreen-copy flow. Skip them for now.

---

# QUICK PLANNING CHECKLIST

When you load a new client end-to-end, the order is:

1. **Client + proof + pains** → master-data-processor makes clean JSON →
   `load_master_data.py` → fills `client_roster`, `case_studies`, `master_sheet_pains`.
2. **Calls** → `ingest_transcript.py` → fills `client_calls` + `call_chunks`.
3. **Copy** → `save_copy.py` → fills `copies` + `copy_components`.
4. **Reasoning (optional)** → `save_direction_sheet.py` → fills `direction_sheets`.
5. **EMBED EVERYTHING** → `python scripts/embed.py` → fills every 🧠 column.
   *(If you skip this, search will not find the new rows.)*
6. **Campaigns + results** → come on their own from Airtable via n8n.
7. **Niche summary** → `niche_synth.py` (after the AI step is wired) → `niche_knowledge`,
   then embed again.

**Remember the weak spot:** everything links by the **text** of `slug` and `niche`.
Spell them identically everywhere or the connections quietly break.
