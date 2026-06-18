"""
load_master_data.py - load clean master data into the DB.

This skill does NOT read xlsx. The master-data-processor skill reads the messy
sheet plus transcripts and emits one clean JSON file in the shape defined in
references/master-data-contract.md. This loader validates that shape, then:

  1. upserts the client row, INCLUDING its Airtable record id
     (airtable_client_id) so campaigns synced from Airtable can later link to
     this client by that id,
  2. upserts case studies on their source_ref,
  3. upserts pains, upgrading needs_more -> confirmed instead of duplicating.

Vectors are left NULL for embed.py. Malformed input is rejected loudly.
"""
import os
import sys
import json
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from connections.supabase import get_conn

PAIN_KINDS = {"pain", "lingo", "dream", "belief", "objection"}
CONFIDENCE = {"confirmed", "needs_more"}


# ---------- validation ----------

def validate(payload):
    errors = []

    client = payload.get("client")
    if not client or not client.get("slug"):
        errors.append("client.slug is required")
    if client and not client.get("client"):
        errors.append("client.client (the display name) is required")

    for i, cs in enumerate(payload.get("case_studies", [])):
        if not cs.get("subject_brand") or not cs.get("after_state"):
            errors.append(f"case_studies[{i}] needs both subject_brand and after_state")

    for i, p in enumerate(payload.get("pains", [])):
        if not p.get("text"):
            errors.append(f"pains[{i}] has empty text")
        if p.get("kind") not in PAIN_KINDS:
            errors.append(f"pains[{i}].kind '{p.get('kind')}' not in {sorted(PAIN_KINDS)}")
        conf = p.get("confidence", "needs_more")
        if conf not in CONFIDENCE:
            errors.append(f"pains[{i}].confidence '{conf}' not in {sorted(CONFIDENCE)}")

    if errors:
        raise ValueError("master data rejected:\n  - " + "\n  - ".join(errors))


# ---------- loaders ----------

def upsert_client(cur, c):
    cur.execute(
        """insert into client_roster (client, slug, airtable_client_id, offer, niche, sub_niche)
           values (%s,%s,%s,%s,%s,%s)
           on conflict (slug) do update set
             client = excluded.client,
             airtable_client_id = coalesce(excluded.airtable_client_id, client_roster.airtable_client_id),
             offer = coalesce(excluded.offer, client_roster.offer),
             niche = coalesce(excluded.niche, client_roster.niche),
             sub_niche = coalesce(excluded.sub_niche, client_roster.sub_niche)
           returning slug, niche, sub_niche""",
        (c.get("client"), c["slug"], c.get("airtable_client_id"),
         c.get("offer"), c.get("niche"), c.get("sub_niche")),
    )
    return cur.fetchone()


def upsert_case_study(cur, cs, slug, niche, sub_niche):
    # dedup on source_ref when present, else plain insert
    src = cs.get("source_ref")
    fields = (
        src,
        cs.get("owner_client_slug", slug),
        cs.get("subject_brand"),
        cs.get("niche", niche),
        cs.get("sub_niche", sub_niche),
        cs.get("service"),
        cs.get("before_state"),
        cs.get("after_state"),
        cs.get("notable_results"),
        cs.get("timeframe"),
        cs.get("mechanism_literal"),
        cs.get("unique_mechanism"),
        cs.get("tier", "D"),
        cs.get("source_url"),
    )
    if src:
        cur.execute("select id from case_studies where source_ref = %s", (src,))
        hit = cur.fetchone()
        if hit:
            cur.execute(
                """update case_studies set
                     owner_client_slug=%s, subject_brand=%s, niche=%s, sub_niche=%s, service=%s,
                     before_state=%s, after_state=%s, notable_results=%s, timeframe=%s,
                     mechanism_literal=%s, unique_mechanism=%s, tier=%s, source_url=%s
                   where id=%s""",
                fields[1:] + (hit[0],),
            )
            return "updated"
    cur.execute(
        """insert into case_studies
           (source_ref, owner_client_slug, subject_brand, niche, sub_niche, service,
            before_state, after_state, notable_results, timeframe,
            mechanism_literal, unique_mechanism, tier, source_url)
           values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
        fields,
    )
    return "inserted"


def upsert_pain(cur, p, slug, niche, sub_niche):
    text = p["text"]
    conf = p.get("confidence", "needs_more")
    cur.execute(
        "select id, confidence from master_sheet_pains where client_slug=%s and item_text=%s",
        (slug, text),
    )
    hit = cur.fetchone()
    if hit:
        # only ever upgrade trust, never duplicate
        if hit[1] == "needs_more" and conf == "confirmed":
            cur.execute(
                "update master_sheet_pains set confidence='confirmed' where id=%s",
                (hit[0],),
            )
            return "upgraded"
        return "skipped"
    cur.execute(
        """insert into master_sheet_pains
           (client_slug, niche, sub_niche, kind, persona, item_text, confidence, source)
           values (%s,%s,%s,%s,%s,%s,%s,%s)""",
        (slug, p.get("niche", niche), p.get("sub_niche", sub_niche), p["kind"],
         p.get("persona"), text, conf, p.get("source")),
    )
    return "inserted"


def load(path):
    with open(path) as f:
        payload = json.load(f)

    validate(payload)

    conn = get_conn()
    counts = {"case_studies": {"inserted": 0, "updated": 0},
              "pains": {"inserted": 0, "upgraded": 0, "skipped": 0}}
    try:
        with conn.cursor() as cur:
            slug, niche, sub_niche = upsert_client(cur, payload["client"])

            for cs in payload.get("case_studies", []):
                r = upsert_case_study(cur, cs, slug, niche, sub_niche)
                counts["case_studies"][r] += 1

            for p in payload.get("pains", []):
                r = upsert_pain(cur, p, slug, niche, sub_niche)
                counts["pains"][r] += 1
        conn.commit()
    finally:
        conn.close()

    print(f"loaded {slug}:")
    print(f"  case studies: {counts['case_studies']}")
    print(f"  pains: {counts['pains']}")
    print("now run: python scripts/embed.py")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", required=True, help="clean master-data JSON (see references/master-data-contract.md)")
    args = ap.parse_args()
    load(args.file)
