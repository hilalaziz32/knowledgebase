"""
save_copy.py - store a finished SMS copy plus its anatomy.

Inserts the copy (char counts computed, vectors NULL, campaign_id NULL) and its
components. Each component verdict is neutral unless the copy is already a winner.
Linking the copy to its campaign happens later by name through MCP, not here.
Run embed.py afterward.

Component types: disarmer | identity | case_line | unique_mechanism | relevance | cta
"""
import os
import sys
import json
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from connections.supabase import get_conn

COPY_FIELDS = [
    "airtable_copy_id", "origin", "client_slug", "case_study_id", "niche", "sub_niche",
    "persona", "sophistication", "channel", "t1", "t2", "lever", "pattern",
    "what_carries", "proof_framing", "unique_mechanism", "pattern_interrupt", "cta",
    "relevance_type", "status", "model_score", "why_it_worked", "why_it_failed",
]


def save(path):
    with open(path) as f:
        c = json.load(f)

    t1 = c.get("t1") or ""
    t2 = c.get("t2") or ""
    status = c.get("status", "draft")

    cols = COPY_FIELDS + ["char_t1", "char_t2", "lineage"]
    vals = [c.get(k) for k in COPY_FIELDS] + [len(t1), len(t2),
            json.dumps(c["lineage"]) if c.get("lineage") is not None else None]
    # defaults
    if not c.get("origin"):
        vals[COPY_FIELDS.index("origin")] = "scaletopia_send"
    if not c.get("channel"):
        vals[COPY_FIELDS.index("channel")] = "sms"
    if not c.get("status"):
        vals[COPY_FIELDS.index("status")] = "draft"

    placeholders = ",".join(["%s"] * len(cols))
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"insert into copies ({','.join(cols)}) values ({placeholders}) returning id",
                vals,
            )
            copy_id = cur.fetchone()[0]

            component_verdict = "winner" if status == "winner" else "neutral"
            component_ids = []
            for comp in c.get("components", []):
                cur.execute(
                    """insert into copy_components
                       (copy_id, component_type, item_text, verdict, niche, persona, lever)
                       values (%s,%s,%s,%s,%s,%s,%s) returning id""",
                    (copy_id, comp.get("component_type"), comp.get("item_text"),
                     component_verdict, c.get("niche"), c.get("persona"), c.get("lever")),
                )
                component_ids.append(cur.fetchone()[0])
        conn.commit()
    finally:
        conn.close()

    print(f"copy {copy_id} saved with {len(component_ids)} components: {component_ids}")
    print("now run: python scripts/embed.py")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", required=True, help="copy JSON with a components[] array")
    args = ap.parse_args()
    save(args.file)
