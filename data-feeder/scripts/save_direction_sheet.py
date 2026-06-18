"""
save_direction_sheet.py - log the AI's reasoning for a campaign.

Optional. Stores the hypothesis (persona -> lever -> case -> mechanism ->
objection -> cta_softness -> why_now -> hypothesis_line), linked to a campaign.
The campaign itself comes from Airtable; this only references it. Link by the
campaign's Airtable id or its name if you have one, else leave it unlinked.
"""
import os
import sys
import json
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from connections.supabase import get_conn

FIELDS = [
    "client_slug", "niche", "persona", "lever", "case_study_id", "unique_mechanism",
    "objection", "cta_softness", "why_now", "hypothesis_line", "outcome_summary",
]


def resolve_campaign(cur, d):
    if d.get("campaign_id"):
        return d["campaign_id"]
    if d.get("campaign_airtable_id"):
        cur.execute("select id from campaigns where airtable_campaign_id = %s", (d["campaign_airtable_id"],))
        hit = cur.fetchone()
        if hit:
            return hit[0]
    if d.get("campaign_name"):
        cur.execute("select id from campaigns where name = %s", (d["campaign_name"],))
        hit = cur.fetchone()
        if hit:
            return hit[0]
    return None


def save(path):
    with open(path) as f:
        d = json.load(f)

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            campaign_id = resolve_campaign(cur, d)
            cols = ["campaign_id"] + FIELDS
            vals = [campaign_id] + [d.get(k) for k in FIELDS]
            placeholders = ",".join(["%s"] * len(cols))
            cur.execute(
                f"insert into direction_sheets ({','.join(cols)}) values ({placeholders}) returning id",
                vals,
            )
            ds_id = cur.fetchone()[0]
        conn.commit()
    finally:
        conn.close()

    link = f"campaign {campaign_id}" if campaign_id else "no campaign linked"
    print(f"direction sheet {ds_id} saved ({link}).")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", required=True, help="direction sheet JSON")
    args = ap.parse_args()
    save(args.file)
