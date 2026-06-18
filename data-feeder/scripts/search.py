"""
search.py - read the memory.

Embeds the query text (RETRIEVAL_QUERY) and calls the matching Postgres RPC.
Types:
  calls        -> search_call_chunks   (filters: --niche, --client)
  copies       -> search_copies        (filters: --niche, --status) also returns positive_rate
  case_studies -> search_case_studies  (filters: --niche, --tier)
  components   -> search_components     (filters: --type, --niche, --verdict)
"""
import os
import sys
import json
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from connections.supabase import get_conn
from connections.gemini import embed_query

RPC = {
    "calls": ("search_call_chunks", ["match_count", "filter_niche", "filter_client"]),
    "copies": ("search_copies", ["match_count", "filter_niche", "filter_status"]),
    "case_studies": ("search_case_studies", ["match_count", "filter_niche", "filter_tier"]),
    "components": ("search_components", ["match_count", "filter_type", "filter_niche", "filter_verdict"]),
}


def search(args):
    fn, params = RPC[args.type]
    qvec = embed_query(args.query)

    arg_map = {
        "match_count": args.match_count,
        "filter_niche": args.niche,
        "filter_client": args.client,
        "filter_status": args.status,
        "filter_tier": args.tier,
        "filter_type": args.comp_type,
        "filter_verdict": args.verdict,
    }
    call_args = [qvec] + [arg_map[p] for p in params]
    placeholders = ",".join(["%s"] * len(call_args))

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(f"select * from {fn}({placeholders})", call_args)
            cols = [c.name for c in cur.description]
            rows = [dict(zip(cols, r)) for r in cur.fetchall()]
    finally:
        conn.close()

    # floats from numeric/vector distance print cleanly as JSON
    print(json.dumps(rows, indent=2, default=str))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--type", required=True, choices=list(RPC.keys()))
    ap.add_argument("--query", required=True)
    ap.add_argument("--match-count", dest="match_count", type=int, default=10)
    ap.add_argument("--niche", default=None)
    ap.add_argument("--client", default=None)
    ap.add_argument("--status", default=None)
    ap.add_argument("--tier", default=None)
    ap.add_argument("--comp-type", dest="comp_type", default=None,
                    help="for components: disarmer|identity|case_line|unique_mechanism|relevance|cta")
    ap.add_argument("--verdict", default=None, help="for components: winner|loser|neutral")
    args = ap.parse_args()
    search(args)
