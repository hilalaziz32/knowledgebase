# Master Data Contract

This is the shape the master-data-processor skill must emit and that
`load_master_data.py` validates. It is the seam between the two skills: one reads
the messy sheet and the transcripts and reasons, the other just stores. Keep this
file in sync with the loader.

The processor outputs ONE JSON file per client. The loader reads it, upserts the
client (with its Airtable record id), the case studies, and the pains, then
leaves embeddings for `embed.py`.

## Shape

```json
{
  "client": {
    "client": "Big Leap",
    "slug": "big_leap",
    "airtable_client_id": "recA1B2C3D4E5F6G7",
    "offer": "SEO / organic traffic",
    "niche": "legal",
    "sub_niche": "personal-injury law"
  },
  "case_studies": [
    {
      "subject_brand": "Transparent Labs",
      "after_state": "grew organic revenue 3.1x in 7 months",
      "before_state": "flat traffic, no content engine",
      "notable_results": "#1 for 40 buyer-intent terms, outranked the category leader",
      "timeframe": "7 months",
      "service": "SEO",
      "mechanism_literal": "built a programmatic comparison-page engine",
      "unique_mechanism": "turned every competitor name into a page that intercepts their buyers",
      "tier": "A",
      "source_url": "https://...",
      "owner_client_slug": "big_leap",
      "niche": "legal",
      "sub_niche": "personal-injury law",
      "source_ref": "Big Leap Master Sheet · Tab 4 · row 12"
    }
  ],
  "pains": [
    {
      "kind": "pain",
      "text": "we rank fine but the traffic never turns into signed cases",
      "persona": "managing partner",
      "confidence": "confirmed",
      "client": "big_leap",
      "niche": "legal",
      "sub_niche": "personal-injury law",
      "source": "call fathom_8842 · chunk 6"
    }
  ]
}
```

## Rules the loader enforces

**client**
- `slug` is required. `client` (display name) is required.
- `airtable_client_id` is the client's Airtable record id. Send it whenever you
  have it. This is the hook campaigns use to link to the client, so a missing one
  means campaigns for this client cannot resolve until it is filled. On re-load,
  an existing id is kept if the new payload omits it.

**case_studies** (array, may be empty)
- Each needs both `subject_brand` and `after_state`. Rows missing either are
  rejected, not silently skipped.
- `source_ref` is the dedup key. Same ref on a re-load updates in place instead of
  duplicating. Use a stable, descriptive ref.
- `tier` defaults to D if omitted. `niche` / `sub_niche` fall back to the client's.

**pains** (array, may be empty)
- `kind` must be one of: pain, lingo, dream, belief, objection.
- `confidence` must be confirmed or needs_more. Default needs_more.
- `text` must be non-empty.
- Dedup is on (client slug + exact text). A pain already stored is never
  duplicated. If it was needs_more and arrives again as confirmed, it gets
  upgraded. Everything else is left as is.
- `persona`, `source`, `niche`, `sub_niche` are optional but send them when known.

## Why pains carry confidence

Pains are rarely written down cleanly. The processor saves what it is sure of now
as `confirmed`, and its best reads as `needs_more`. As more transcripts land, the
same pain re-emitted as `confirmed` upgrades the stored row. So a client's pain
picture fills in over time instead of needing a perfect sheet on day one.
