# Scaletopia Evergreen — Ingestion Plan (MVP + agents)

How a client's data gets from raw files → clean rows → embeddings → searchable
memory. Written around the real Kynship files and the existing `data-feeder`
scripts. Easy English, but every column is mapped to **what fills it and when**.

---

## 0. The one architecture decision (read first)

Your idea: a frontend button → an AI agent that has **Supabase MCP** + an
**embedding tool** → the agent writes straight into the DB.

The existing skill has a hard rule against agents free-writing SQL, because that
is how embeddings drift and dedup breaks. So we use a **hybrid** that keeps your
agent idea but makes writes safe:

```
Frontend button
   → API endpoint
       → AI AGENT does the THINKING (parse messy paste → clean structured JSON)
       → WRITER does the SAVING (one validated insert path + dedup)  ← not the agent
       → EMBEDDER fills the vectors (one path, idempotent)
   → returns "saved X rows, embedded Y" to the screen
```

- **Agent = judgment.** Read the messy CSV / form / transcript, pull out the real
  fields, score the tier, find the pains. This is where Claude/Gemini is used.
- **Writer = deterministic.** Takes the agent's clean JSON and inserts it, with
  dedup. This is the existing `load_master_data.py` / `save_copy.py` logic, wrapped
  behind an endpoint.
- **Embedder = one path.** `embed.py` (Gemini `gemini-embedding-001`). Never embed
  inside the agent — it would drift from the search side.

You still get the exact UX you described (click → paste → it breaks them and
saves). The agent just doesn't hold the SQL pen.

> If you instead want the agent to write directly via MCP for the MVP speed, that
> is possible, but then YOU own keeping the insert shape + embedding model
> identical to the search side. The hybrid removes that risk. **Recommended: hybrid.**

---

## 1. What we have for a client at the start (real Kynship inputs)

| Source file | What's in it | Lands in table(s) |
|---|---|---|
| `kynship-onboarding-form.txt` | QA pairs: location, revenue band, ICP job titles, value statement, "what's different" | `client_roster` (+ some pains/beliefs) |
| Tab 2 `ACCOUNT TARGETING.csv` | One row per industry: 3-5 pains, dream outcomes, current solution, mistaken beliefs, dream ICP, recognizable logos | `master_sheet_pains` |
| Tab 3 `PERSONA TARGETING.csv` | One row per job title: responsibilities, pains *in their words*, current solution, what they care about, decision authority | `master_sheet_pains` (persona-tagged) |
| Tab 4 `CASE STUDIES.csv` | Client name+site, sub-niche, service, before, after, notable results, timeframe, unique mechanism, tier | `case_studies` |
| Tab 5 `CASE STUDY EXAMPLE & TIERING GUIDE.csv` | The S/A/B/C/D rubric + a worked example | **Not stored** — it's the rubric the agent uses to set `tier` |
| `transcripts/` | Raw call transcripts | `client_calls` + `call_chunks` + discovered `master_sheet_pains` |
| (later) Airtable | Campaigns, copy, metrics | `campaigns`, `copies`, `copy_metrics` |

---

## 2. The agents (4 total)

Your two agents, plus two the data already needs.

### Agent A — Case Study Agent
**Trigger:** click client → "paste case studies" (or upload Tab 4 CSV).
**Does:**
1. Split the paste into separate case studies (one object each).
2. For each, extract: subject_brand, before_state, after_state, notable_results,
   timeframe, service, mechanism_literal, unique_mechanism.
3. **Score `tier`** using the Tab 5 rubric (S = transformation + mechanism + logo;
   A = two of those; B = revenue+timeframe; C/D = metric-only).
4. Build a stable `source_ref` (e.g. `Kynship Master Sheet · Tab 4 · row 7`).
5. Emit clean JSON → Writer inserts into `case_studies` (dedup on source_ref).

### Agent B — Onboarding + Account/Persona Agent
**Trigger:** click client → "paste onboarding form / account & persona tabs".
**Does:**
1. From the onboarding form: build the `client_roster` row (display name, slug,
   offer/value statement, niche, sub_niche; airtable_client_id if known).
2. From Tab 2: emit pains, dreams, mistaken-beliefs→objection, lingo — niche-level.
3. From Tab 3: emit persona-level pains + lingo, tagged with the job title.
4. Mark `confidence`: things stated plainly = `confirmed`; inferred = `needs_more`.
5. Emit clean JSON → Writer upserts `client_roster` + `master_sheet_pains`.

### Agent C — Transcript Agent
**Trigger:** endpoint receives a transcript (file or text).
**Does:**
1. Save the full raw text → `client_calls` (dedup on `source_call_id`).
2. Chunk it turn-by-turn (~400 tokens, 50 overlap) → `call_chunks`.
3. Read the chunks and pull out NEW pains / lingo / objections → `master_sheet_pains`
   (as `needs_more`, so they upgrade later if the sheet confirms them).
4. Writer inserts; Embedder vectors the chunks + new pains.

### Agent D — Niche Synthesis Agent
**Trigger:** "synthesize the {niche} niche" (Friday or on demand).
**Does:** gather all pains/calls/winning-copy in the niche → cluster duplicates →
**one LLM call** writes the summary → upsert `niche_knowledge`.
(The gather+cluster already exist in `niche_synth.py`; only the LLM call is unwired.)

---

## 3. Column-by-column: what gets filled, by which agent, WHEN

### `client_roster` — filled by Agent B, at onboarding
| Column | Filled with | When / source |
|---|---|---|
| `client` | "Kynship" | Agent B from form |
| `slug` | `kynship` | Agent B (slugify name) |
| `airtable_client_id` | rec… | When known (form or Airtable); else later |
| `offer` | the value statement | Agent B from form |
| `niche` | e.g. `DTC ecom` | Agent B from form/Tab 2 |
| `sub_niche` | e.g. `supplements` | Agent B |
| `signature_case_study_ids` | best case study IDs | **After** Agent A runs (we know IDs then) |
| `status` | `active` | Set on create |
| `id`, `created_at`, `updated_at` | auto | DB |

### `case_studies` — filled by Agent A, after client exists
| Column | Filled with | When / source |
|---|---|---|
| `subject_brand` | "Transparent Labs" | Agent A (**required**) |
| `after_state` | "$2M → $26M, 8:1 ROAS" | Agent A (**required**) |
| `before_state` | "stuck at $2M, generic creative" | Agent A |
| `notable_results` | "15-18mo creative lifespan, 5:1 blended" | Agent A |
| `timeframe` | "2 years" | Agent A |
| `service` | "FB ads, creative" | Agent A |
| `mechanism_literal` | "humor-driven entertaining ads" | Agent A |
| `unique_mechanism` | "made supplement science unskippable" | Agent A |
| `tier` | `S` | Agent A via Tab 5 rubric |
| `source_ref` | "Kynship · Tab 4 · row 3" | Agent A (**dedup key**) |
| `owner_client_slug` | `kynship` | Agent A (current client) |
| `niche`/`sub_niche` | falls back to client's | Agent A |
| `source_url` | the website | Agent A |
| `result_embedding` 🧠 | vector | **Embedder later** |
| `unique_mechanism_embedding` 🧠 | vector | **Embedder later** |
| `niche_embedding` 🧠 | vector | **Embedder later** |

### `master_sheet_pains` — filled by Agent B (sheets) + Agent C (transcripts)
| Column | Filled with | When / source |
|---|---|---|
| `client_slug` | `kynship` | B & C |
| `kind` | pain / lingo / dream / belief / objection | B from Tab2/Tab3; C from transcript |
| `item_text` | the actual pain/phrase (**required**) | B & C |
| `persona` | "VP of Marketing" | B from Tab 3; C if clear |
| `confidence` | `confirmed` (sheet) / `needs_more` (inferred or transcript) | B & C |
| `niche`/`sub_niche` | falls back to client's | B & C |
| `source` | "Tab 2 row 1" or "call kynship_disc_01 · chunk 6" | B & C |
| `embedding` 🧠 | vector | **Embedder later** |

> Dedup: same `client_slug + exact text` is never duplicated. A `needs_more` pain
> that re-arrives as `confirmed` is **upgraded**. So transcript guesses get
> promoted when the sheet confirms them.

### `client_calls` — filled by Agent C
| Column | Filled with | When / source |
|---|---|---|
| `client_slug` | resolved from client name | Agent C |
| `title` | "Discovery call" | Agent C / input |
| `call_date` | date | input |
| `source` | "fathom" / "manual" | input |
| `source_call_id` | `kynship_disc_01` | input (**dedup key**) |
| `participants` | names | input |
| `raw_transcript` | full text | Agent C |

### `call_chunks` — filled by Agent C (auto-chunked)
| Column | Filled with | When |
|---|---|---|
| `call_id` | parent call | Agent C |
| `client_slug` | `kynship` | Agent C |
| `niche` | client's niche | Agent C (stamped) |
| `chunk_index` | 0,1,2… | Agent C |
| `chunk_text` | the chunk words | Agent C |
| `embedding` 🧠 | vector | **Embedder later** |

### `niche_knowledge` — filled by Agent D (one row per niche)
| Column | Filled with | When |
|---|---|---|
| `niche` | "DTC ecom" | Agent D (key) |
| `top_pains` | clustered pains + client_count | Agent D LLM |
| `shared_lingo` | buyer phrases | Agent D LLM |
| `dream_outcomes` | what they want | Agent D LLM |
| `winning_levers` | levers that scored | Agent D LLM |
| `commonalities_summary` | 2-4 sentence summary | Agent D LLM |
| `source_client_slugs` | who fed it | Agent D |
| `refreshed_at` | now | Agent D |
| `summary_embedding` 🧠 | vector | **Embedder later** |

---

## 4. Campaigns + copy + metrics (the Airtable side)

You said: **campaigns are created from Airtable when you sync on client id, then we
fill some.** Exactly right. Split it like this:

### `campaigns` — synced from Airtable by n8n on `airtable_client_id`
Filled automatically from Airtable: `airtable_campaign_id`, `airtable_client_id`,
`name`, `client_slug` (resolved), `niche`, `persona`, `segment`, `channel`,
`list_source`, `start_date`.

**Then WE fill (by hand / via MCP, after sync):**
| Column | Who fills | When |
|---|---|---|
| `angle` | us | when we set the campaign's strategic angle |
| `notes` | us | running notes |

(The sync depends on `client_roster.airtable_client_id` being present — that's why
Agent B must capture it. No id = campaign can't resolve to the client.)

### `copies` + `copy_components` — saved when we finish writing copy
- `save_copy.py` inserts the copy, auto-counts `char_t1`/`char_t2`, inserts the 6
  components (disarmer, identity, case_line, unique_mechanism, relevance, cta).
- `campaign_id` is **left NULL at save**, then linked to the campaign by name via
  MCP afterward.
- All 🧠 columns (`full_copy_embedding`, `t1_embedding`, `unique_mechanism_embedding`,
  component `embedding`) filled by Embedder.

### `copy_metrics` — synced from Airtable by n8n
`sent`, `positive_responses`, `booked_calls`, period, region. Feeds the
`copy_performance` view → real `positive_rate` → which copies are true winners.

---

## 5. The embedding step (always last)

After ANY write above, run the Embedder once. It walks the registry
(`config/embed_registry.json`), finds every row with a NULL vector + non-empty
text, embeds with Gemini, writes back. Idempotent — safe to run twice.

Columns it fills: call_chunks.embedding, case_studies ×3, master_sheet_pains.embedding,
copies ×3, copy_components.embedding, niche_knowledge.summary_embedding.

**Rule: if you skip embed, search will not see the new rows.**

---

## 6. MVP order of operations (one client end-to-end)

For the MVP (Chamber Media or Kynship), run in THIS order — each step needs the one before:

1. **Agent B** → create `client_roster` (must exist first) + load Tab 2/Tab 3 pains.
2. **Agent A** → load `case_studies` (needs client). Then backfill
   `client_roster.signature_case_study_ids` with the S/A tier IDs.
3. **Agent C** → for each transcript: `client_calls` + `call_chunks` + new pains.
4. **Embedder** → fill every vector.
5. **Airtable sync** → `campaigns` + `copy_metrics` land by client id.
6. **save_copy** when copy is written → `copies` + `copy_components`; link to campaign; embed.
7. **Agent D** → `niche_knowledge` once enough clients exist in the niche.

**Why this order:** a client must exist before its calls/cases/copy can attach
(foreign anchor = `client_slug`). Embeddings come after writes. Campaigns and
metrics arrive on their own from Airtable.

---

## 7. The 4-6 week sprint framework (to present to the team)

| Week | Focus | Output |
|---|---|---|
| 1 | **System design + schema lock** | Confirm tables, lock niche/slug naming, freeze the JSON contracts for each agent |
| 2 | **Writers + Embedder as endpoints** | Wrap `load_master_data` / `save_copy` / `ingest_transcript` / `embed` behind APIs; test on Kynship CSVs |
| 3 | **Agents A & B** | Case Study Agent + Onboarding/Account/Persona Agent producing valid JSON from real paste; frontend buttons |
| 4 | **Agent C + backfill** | Transcript Agent live; backfill Chamber Media's heavy historical volume |
| 5 | **Airtable sync + niche synth** | n8n campaign/metrics mirror on client id; wire Agent D's LLM call |
| 6 | **Live triggers + search QA** | End-to-end: paste → save → embed → search returns it; weight winners by real positive_rate |

**Biggest risk to watch the whole time:** everything links by the *text spelling*
of `slug` and `niche`. Lock the naming in Week 1 or the graph quietly breaks.

---

## 8. Open questions to settle

1. **Hybrid vs. agent-writes-directly** — recommend hybrid (Section 0). Confirm.
2. **Embedding model** — skill uses Gemini `gemini-embedding-001`. Your agent note
   mentioned OpenAI `text-embedding-3-small`. **Must pick ONE** for write + search,
   or search breaks. Recommend staying on Gemini to match the existing search RPCs.
3. **MVP client** — Chamber Media (heavy volume) or Kynship (data already here)?
4. **airtable_client_id** — where do we read it at onboarding so campaigns can link?
