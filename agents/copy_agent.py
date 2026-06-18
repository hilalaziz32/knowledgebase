"""copy_agent.py - save a finished copy + its components, then embed.

Inserts the copy (char counts computed, vectors NULL) and its six components,
verdict neutral unless the copy is already a winner. campaign_id may be passed now
or linked later via the frontend. Run embed afterward (this script does it).

Usage:
  python copy_agent.py --file copy.json
  python copy_agent.py --file copy.json --campaign-id 12     # link at save time

copy.json shape:
  {
    "client_slug": "chamber_media", "niche": "DTC ecom", "persona": "VP Marketing",
    "t1": "...", "t2": "...", "lever": "proof", "pattern": "...", "status": "draft",
    "unique_mechanism": "...", "cta": "...",
    "components": [{"component_type":"disarmer","item_text":"..."}, ...]
  }
"""
import os
import sys
import json
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from connections.supabase import get_conn, resolve_client
from shared.writers import save_copy, link_copy_to_campaign
from shared.embed import embed_all


def run(path, campaign_id):
    with open(path) as f:
        c = json.load(f)

    conn = get_conn()
    try:
        # resolve/validate client
        slug, niche, sub = resolve_client(conn, c.get("client_slug") or c.get("client"))
        c["client_slug"] = slug
        c.setdefault("niche", niche)
        c.setdefault("sub_niche", sub)
        if campaign_id:
            c["campaign_id"] = campaign_id

        with conn.cursor() as cur:
            copy_id, comp_ids = save_copy(cur, c)
            if campaign_id:
                link_copy_to_campaign(cur, copy_id, campaign_id)
        conn.commit()
        print(f"copy {copy_id} saved with {len(comp_ids)} components"
              + (f", linked to campaign {campaign_id}" if campaign_id else ""))
        n = embed_all(conn, only_tables={"copies", "copy_components"})
        print(f"embedded {n} rows.")
        print(json.dumps({"copy_id": copy_id, "component_ids": comp_ids}))
    finally:
        conn.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", required=True, help="copy JSON with a components[] array")
    ap.add_argument("--campaign-id", type=int, default=None)
    args = ap.parse_args()
    run(args.file, args.campaign_id)
