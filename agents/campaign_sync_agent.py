"""Agent E — Campaign sync from Airtable.

Reads the campaigns linked to a client in the Airtable "Operations & Data
Analytics" base (📢 Campaigns table) and upserts them into the Evergreen DB
campaigns table, keyed on the Airtable record id. Uses the AIRTABLE token from
.env directly (NOT the MCP server), so the source of truth is your own key.

The campaign Name encodes the strategy, e.g.:
    "Kynship - Household Goods | 5-200E | USA, CA | V4"
     <client> - <vertical/angle>  | <segment> | <region> | <variant>
We parse those parts into angle / segment / notes. niche falls back to the
client's niche from client_roster.

The client must already exist in client_roster (run onboarding_agent first), so
campaigns resolve to a real client_slug.

Usage:
  python campaign_sync_agent.py --client kynship
  python campaign_sync_agent.py --client kynship --dry-run
"""
import os
import sys
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from connections.supabase import get_conn
from connections.airtable import get_record, list_records

CAMPAIGNS_TABLE = "📢 Campaigns"
CLIENTS_TABLE = "📂 Clients"

# Airtable Campaign Type -> our channel
CHANNEL = {"SMS": "sms", "EmailBison": "email", "Email": "email"}


def parse_name(name):
    """Parse a campaign name into {angle, segment, region, variant}. Handles both
       'Client - Angle | Segment | Region | Variant'  and
       'Client | Angle | Segment | Region'  layouts. Tolerant of missing parts."""
    out = {"angle": None, "segment": None, "region": None, "variant": None}
    if not name:
        return out
    segs = [s.strip() for s in name.split("|") if s.strip()]
    if not segs:
        return out
    if "-" in segs[0]:
        # 'Client - Angle' in the first pipe-segment; rest are segment/region/variant
        out["angle"] = segs[0].split("-", 1)[1].strip() or None
        rest = segs[1:]
    else:
        # 'Client' alone in the first segment; angle is the next pipe-segment
        out["angle"] = segs[1] if len(segs) > 1 else None
        rest = segs[2:]
    if len(rest) > 0:
        out["segment"] = rest[0]         # size band, e.g. 5-200E
    if len(rest) > 1:
        out["region"] = rest[1]          # e.g. USA, CA
    if len(rest) > 2:
        out["variant"] = rest[2]         # e.g. V4
    return out


def get_client_airtable_id(cur, slug):
    cur.execute("select airtable_client_id, niche from client_roster where slug=%s", (slug,))
    row = cur.fetchone()
    if not row:
        raise SystemExit(f"client '{slug}' not in client_roster. Run onboarding_agent first.")
    return row[0], row[1]


def upsert_campaign(cur, rec, slug, client_niche, airtable_client_id):
    """Dedup on airtable_campaign_id (the Airtable record id)."""
    f = rec["fields"]
    name = (f.get("Name") or "").strip()
    parsed = parse_name(name)
    channel = CHANNEL.get(f.get("Campaign Type"), None)
    note_bits = []
    if parsed["region"]:
        note_bits.append(f"region: {parsed['region']}")
    if parsed["variant"]:
        note_bits.append(f"variant: {parsed['variant']}")
    if f.get("Campaign Status"):
        note_bits.append(f"status: {f['Campaign Status']}")
    if f.get("Campaign ID"):
        note_bits.append(f"ext_id: {f['Campaign ID']}")
    notes = "; ".join(note_bits) or None

    vals = {
        "airtable_campaign_id": rec["id"],
        "airtable_client_id": airtable_client_id,
        "name": name,
        "client_slug": slug,
        "niche": client_niche,            # campaign niche defaults to client's niche
        "segment": parsed["segment"],
        "angle": parsed["angle"],
        "channel": channel,
        "notes": notes,
    }

    cur.execute("select id from campaigns where airtable_campaign_id=%s", (rec["id"],))
    hit = cur.fetchone()
    if hit:
        cur.execute(
            """update campaigns set airtable_client_id=%s, name=%s, client_slug=%s,
                 niche=coalesce(niche,%s), segment=%s, angle=coalesce(angle,%s),
                 channel=%s, notes=coalesce(notes,%s), updated_at=now()
               where id=%s""",
            (vals["airtable_client_id"], vals["name"], vals["client_slug"], vals["niche"],
             vals["segment"], vals["angle"], vals["channel"], vals["notes"], hit[0]),
        )
        return "updated", vals
    cur.execute(
        """insert into campaigns
           (airtable_campaign_id, airtable_client_id, name, client_slug, niche,
            segment, angle, channel, notes)
           values (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
        (vals["airtable_campaign_id"], vals["airtable_client_id"], vals["name"],
         vals["client_slug"], vals["niche"], vals["segment"], vals["angle"],
         vals["channel"], vals["notes"]),
    )
    return "inserted", vals


def run(slug, airtable_client_id_arg, dry_run):
    conn = get_conn()
    try:
        client_niche = None
        with conn.cursor() as cur:
            try:
                airtable_client_id, client_niche = get_client_airtable_id(cur, slug)
            except SystemExit:
                # In dry-run we can preview without the client loaded yet.
                if not (dry_run and airtable_client_id_arg):
                    raise
                airtable_client_id = None
        airtable_client_id = airtable_client_id or airtable_client_id_arg
        if not airtable_client_id:
            raise SystemExit("no airtable_client_id on the client and none passed via --airtable-id.")

        # the client's record holds the linked campaign record ids
        client_rec = get_record(CLIENTS_TABLE, airtable_client_id)
        camp_ids = client_rec.get("📢 Campaigns", [])
        print(f"client '{slug}' ({airtable_client_id}) has {len(camp_ids)} linked campaigns in Airtable.")

        counts = {"inserted": 0, "updated": 0}
        with conn.cursor() as cur:
            for cid in camp_ids:
                rec = {"id": cid, "fields": get_record(CAMPAIGNS_TABLE, cid)}
                if dry_run:
                    p = parse_name(rec["fields"].get("Name"))
                    print(f"  [dry] {rec['fields'].get('Name','?')[:55]:55} -> angle={p['angle']}, "
                          f"segment={p['segment']}, channel={CHANNEL.get(rec['fields'].get('Campaign Type'))}")
                    continue
                action, _ = upsert_campaign(cur, rec, slug, client_niche, airtable_client_id)
                counts[action] += 1
        if not dry_run:
            conn.commit()
            print(f"campaigns synced: {counts}")
        else:
            print("dry run — nothing written.")
    finally:
        conn.close()
    print("done.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--client", required=True, help="client slug (must exist in client_roster)")
    ap.add_argument("--airtable-id", default=None, help="override client's Airtable record id")
    ap.add_argument("--dry-run", action="store_true", help="show what would sync, write nothing")
    args = ap.parse_args()
    run(args.client, args.airtable_id, args.dry_run)
