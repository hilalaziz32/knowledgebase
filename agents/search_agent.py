"""search_agent.py - semantic search over the Evergreen memory.

Embeds the query with Gemini (RETRIEVAL_QUERY) and runs pgvector cosine search
against the chosen content type. Prints JSON results. Used by the frontend search
page and usable from the CLI.

Types:
  pains        -> master_sheet_pains.embedding (item_text)
  calls        -> call_chunks.embedding (chunk_text)
  case_studies -> case_studies.result_embedding (after_state + notable_results)
  copies       -> copies.full_copy_embedding (t1 + t2)  [+ real positive_rate]
  components   -> copy_components.embedding (item_text)

Usage:
  python search_agent.py --type pains --query "rising CAC on meta" --niche "DTC ecom" --limit 10
"""
import os
import sys
import json
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from connections.supabase import get_conn
from connections.gemini import embed_query

# type -> (table, vector_col, select_cols, optional niche filter col)
SPECS = {
    "pains": (
        "master_sheet_pains", "embedding",
        "id, client_slug, kind, persona, item_text, confidence", "niche",
    ),
    "calls": (
        "call_chunks", "embedding",
        "id, client_slug, chunk_text", "niche",
    ),
    "case_studies": (
        "case_studies", "result_embedding",
        "id, owner_client_slug as client_slug, subject_brand, tier, after_state, unique_mechanism", "niche",
    ),
    "copies": (
        "copies", "full_copy_embedding",
        "id, client_slug, status, lever, t1, t2", "niche",
    ),
    "components": (
        "copy_components", "embedding",
        "id, component_type, item_text, verdict, persona, lever", "niche",
    ),
}


def route_niches(cur, qvec, top=2, min_score=0.55):
    """Stage 1: route the query to the most relevant niche(s) by comparing it to
    each niche_knowledge.summary_embedding. Returns [(niche, score), ...]."""
    cur.execute(
        """select niche, 1 - (summary_embedding <=> %s::vector) as score
           from niche_knowledge
           where summary_embedding is not null
           order by summary_embedding <=> %s::vector
           limit %s""",
        (qvec, qvec, top),
    )
    rows = [(n, round(float(s), 4)) for n, s in cur.fetchall()]
    return [r for r in rows if r[1] >= min_score] or rows  # keep best even if below cutoff


def run(stype, query, niche, status, limit, route=False):
    if stype not in SPECS:
        raise SystemExit(f"unknown type '{stype}'. one of {sorted(SPECS)}")
    table, vec, cols, niche_col = SPECS[stype]
    qvec = embed_query(query)

    routed = []
    conn0 = None
    where = [f"{vec} is not null"]
    params = []

    # Stage 1: niche routing (only when no explicit niche was given)
    if route and not niche and niche_col:
        conn0 = get_conn()
        with conn0.cursor() as rc:
            routed = route_niches(rc, qvec)
        niches = [n for n, _ in routed]
        if niches:
            where.append(f"{niche_col} = ANY(%s)")
            params.append(niches)
    elif niche and niche_col:
        where.append(f"{niche_col} = %s")
        params.append(niche)

    if status and stype == "copies":
        where.append("status = %s")
        params.append(status)
    where_sql = " and ".join(where)

    sql = (
        f"select {cols}, 1 - ({vec} <=> %s::vector) as score "
        f"from {table} where {where_sql} "
        f"order by {vec} <=> %s::vector limit %s"
    )
    args = [qvec] + params + [qvec, limit]

    conn = conn0 or get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, args)
            colnames = [d[0] for d in cur.description]
            rows = [dict(zip(colnames, r)) for r in cur.fetchall()]

        # for copies, attach the real positive_rate from the performance view
        if stype == "copies" and rows:
            ids = [r["id"] for r in rows]
            with conn.cursor() as cur:
                cur.execute(
                    "select copy_id, positive_rate, sent, booked from copy_performance where copy_id = any(%s)",
                    (ids,),
                )
                perf = {r[0]: {"positive_rate": float(r[1]) if r[1] is not None else None,
                               "sent": r[2], "booked": r[3]} for r in cur.fetchall()}
            for r in rows:
                r.update(perf.get(r["id"], {}))

        for r in rows:
            if "score" in r and r["score"] is not None:
                r["score"] = round(float(r["score"]), 4)
        print(json.dumps(
            {"type": stype, "query": query, "routed": [{"niche": n, "score": s} for n, s in routed],
             "results": rows},
            default=str,
        ))
    finally:
        conn.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--type", required=True)
    ap.add_argument("--query", required=True)
    ap.add_argument("--niche", default=None)
    ap.add_argument("--status", default=None, help="copies only: winner/loser/...")
    ap.add_argument("--limit", type=int, default=10)
    ap.add_argument("--route", action="store_true", help="route to the best niche(s) first, then search within")
    args = ap.parse_args()
    run(args.type, args.query, args.niche, args.status, args.limit, args.route)
