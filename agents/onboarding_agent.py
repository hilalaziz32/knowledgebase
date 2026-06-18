"""Agent B — Onboarding / Account / Persona.

Takes the messy onboarding form text plus (optionally) the ACCOUNT TARGETING and
PERSONA TARGETING tab text, and:
  1. builds + upserts the client_roster row (this must exist before anything else),
  2. extracts pains / dreams / beliefs(->objection) / lingo and upserts them into
     master_sheet_pains,
  3. embeds the new pains.

Gemini does the extraction; the dedup-safe writers do the saving. Run from the
agents/ folder so the package imports resolve.

Usage:
  python onboarding_agent.py --client "Kynship" --slug kynship \
      --airtable-id recncshNnMmK4OTei \
      --form clients/kynship/onboarding-form.txt \
      --account clients/kynship/account-targeting.csv \
      --persona clients/kynship/persona-targeting.csv
"""
import os
import sys
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from connections.supabase import get_conn
from connections.gemini import extract_json
from shared.writers import upsert_client, upsert_pain
from shared.embed import embed_all

SYSTEM = (
    "You are a B2B GTM data extractor for a cold-outreach agency. You read messy "
    "client intake material and return STRICT JSON only. Never invent facts; if a "
    "field is unknown leave it null or omit it."
)

PROMPT = """From the client material below, return STRICT JSON matching exactly:

{{
  "client": {{
    "offer": "one clean sentence describing what they sell / their value statement",
    "niche": "broad industry, e.g. 'DTC ecom'",
    "sub_niche": "more specific, e.g. 'supplements' (null if unclear)"
  }},
  "pains": [
    {{
      "kind": "pain | lingo | dream | belief | objection",
      "text": "the item in the buyer's own words, concise",
      "persona": "job title this belongs to, or null",
      "confidence": "confirmed if stated plainly in the material, else needs_more",
      "source": "short pointer e.g. 'Account Tab · Supplements row' or 'Onboarding form'"
    }}
  ]
}}

Rules:
- kind meanings: pain = a struggle; dream = a desired outcome; belief = a mistaken
  belief / objection about the service; objection = a sales objection; lingo = a
  distinctive phrase real buyers use.
- Pull EVERY distinct pain/dream/belief/objection you can find. One per array item.
- Tag persona-tab items with their job title. Account-tab items can leave persona null.
- Keep text short and in the buyer's voice. Do not merge multiple ideas into one.

CLIENT MATERIAL:
---
{material}
---"""


def _read(path):
    if not path:
        return ""
    with open(path, encoding="utf-8", errors="ignore") as f:
        return f.read()


def run(client, slug, airtable_id, niche_hint, sub_niche_hint, form_path, account_path, persona_path):
    material = "\n\n".join(filter(None, [
        f"## ONBOARDING FORM\n{_read(form_path)}" if form_path else "",
        f"## ACCOUNT TARGETING TAB\n{_read(account_path)}" if account_path else "",
        f"## PERSONA TARGETING TAB\n{_read(persona_path)}" if persona_path else "",
    ]))
    if not material.strip():
        raise SystemExit("No input. Pass at least one of --form / --account / --persona.")

    print("extracting with Gemini ...")
    data = extract_json(PROMPT.format(material=material), system=SYSTEM)

    c = data.get("client", {})
    client_row = {
        "client": client,
        "slug": slug,
        "airtable_client_id": airtable_id,
        "offer": c.get("offer"),
        "niche": niche_hint or c.get("niche"),
        "sub_niche": sub_niche_hint or c.get("sub_niche"),
    }
    pains = data.get("pains", [])

    conn = get_conn()
    counts = {"inserted": 0, "upgraded": 0, "skipped": 0}
    try:
        with conn.cursor() as cur:
            slug_, niche_, sub_ = upsert_client(cur, client_row)
            for p in pains:
                try:
                    counts[upsert_pain(cur, p, slug_, niche_, sub_)] += 1
                except ValueError as e:
                    print(f"  skipped a pain: {e}")
        conn.commit()
        print(f"client '{slug_}' upserted (niche={niche_}, sub={sub_}).")
        print(f"pains: {counts}")
        n = embed_all(conn, only_tables={"master_sheet_pains"})
        print(f"embedded {n} pain rows.")
    finally:
        conn.close()
    print("done.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--client", required=True, help="display name, e.g. Kynship")
    ap.add_argument("--slug", required=True, help="slug, e.g. kynship")
    ap.add_argument("--airtable-id", default=None, help="client's Airtable record id")
    ap.add_argument("--niche", default=None, help="override niche")
    ap.add_argument("--sub-niche", default=None, help="override sub_niche")
    ap.add_argument("--form", default=None)
    ap.add_argument("--account", default=None)
    ap.add_argument("--persona", default=None)
    args = ap.parse_args()
    run(args.client, args.slug, args.airtable_id, args.niche, args.sub_niche,
        args.form, args.account, args.persona)
