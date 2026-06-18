"""
niche_synth.py - build the cross-client niche summary.

Done here: gather every client's pains, call evidence, and winning copy in the
niche, then cluster near-duplicate items by cosine similarity so the same point
made by three clients counts as one (with client_count).

Stubbed for Hilal: the single LLM call that turns the clusters into the
commonalities summary + structured JSON. The prompt and the exact output schema
are written below, so wiring it is just choosing Gemini or Claude and calling it.

Run embed.py afterward to fill the new summary_embedding.
"""
import os
import sys
import json
import argparse

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from connections.supabase import get_conn

CLUSTER_THRESHOLD = 0.82  # cosine; items above this are treated as the same point


# ---------- gather ----------

def gather(cur, niche):
    cur.execute(
        """select client_slug, kind, persona, item_text, confidence, embedding
           from master_sheet_pains
           where niche = %s and embedding is not null""",
        (niche,),
    )
    pains = cur.fetchall()

    cur.execute(
        """select client_slug, chunk_text, embedding
           from call_chunks
           where niche = %s and embedding is not null""",
        (niche,),
    )
    calls = cur.fetchall()

    cur.execute(
        """select client_slug, lever, pattern, t1, t2, full_copy_embedding
           from copies
           where niche = %s and status = 'winner' and full_copy_embedding is not null""",
        (niche,),
    )
    winners = cur.fetchall()

    return pains, calls, winners


# ---------- cluster ----------

def cluster(items, embedding_index):
    """
    Greedy cosine clustering. items is a list of tuples, embedding_index is the
    position of the (already L2-normalized) vector in each tuple. Returns a list
    of clusters, each a list of items. client_count is computed by the caller.
    """
    vecs = [np.asarray(it[embedding_index], dtype=float) for it in items]
    used = [False] * len(items)
    clusters = []
    for i in range(len(items)):
        if used[i]:
            continue
        group = [items[i]]
        used[i] = True
        for j in range(i + 1, len(items)):
            if used[j]:
                continue
            sim = float(np.dot(vecs[i], vecs[j]))  # both normalized -> dot == cosine
            if sim >= CLUSTER_THRESHOLD:
                group.append(items[j])
                used[j] = True
        clusters.append(group)
    return clusters


def pains_to_clusters(pains):
    clusters = cluster(pains, embedding_index=5)
    out = []
    for g in clusters:
        clients = sorted({row[0] for row in g})
        out.append({
            "pain": g[0][3],                       # representative text
            "client_count": len(clients),
            "examples": [row[3] for row in g[:3]],
            "clients": clients,
        })
    out.sort(key=lambda c: c["client_count"], reverse=True)
    return out


# ---------- synthesize (STUB) ----------

SYNTH_PROMPT = """You are summarizing what every Scaletopia client in one niche
has taught us, so a new campaign in this niche starts informed.

Niche: {niche}

Clustered pains (each with how many distinct clients raised it):
{pain_clusters}

Sample buyer language from calls and master sheets:
{lingo_samples}

Winning copy levers seen in this niche:
{winning_levers}

Return STRICT JSON, no prose, matching exactly:
{{
  "commonalities_summary": "2-4 sentences on the recurring wall buyers in this niche hit",
  "top_pains": [{{"pain": "...", "client_count": 0, "examples": ["..."]}}],
  "shared_lingo": ["word or phrase real buyers use"],
  "dream_outcomes": ["what they actually want"],
  "winning_levers": ["lever names that scored here, most common first"]
}}"""


def synthesize_with_llm(niche, pain_clusters, lingo_samples, winning_levers):
    """
    TODO (Hilal): wire one LLM call here. Build the prompt with SYNTH_PROMPT.format(...),
    send it to Gemini or Claude, parse the response as JSON, and validate it has the
    five keys above before returning. Until this is wired, synthesis cannot run.
    """
    raise NotImplementedError(
        "Wire the synthesis LLM call. The prompt is SYNTH_PROMPT, the output schema is "
        "in the prompt. Return a dict with keys: commonalities_summary, top_pains, "
        "shared_lingo, dream_outcomes, winning_levers."
    )


# ---------- upsert ----------

def upsert_niche_knowledge(cur, niche, result, source_clients):
    cur.execute(
        """insert into niche_knowledge
           (niche, top_pains, shared_lingo, dream_outcomes, winning_levers,
            commonalities_summary, source_client_slugs, refreshed_at, summary_embedding)
           values (%s,%s,%s,%s,%s,%s,%s, now(), null)
           on conflict (niche) do update set
             top_pains = excluded.top_pains,
             shared_lingo = excluded.shared_lingo,
             dream_outcomes = excluded.dream_outcomes,
             winning_levers = excluded.winning_levers,
             commonalities_summary = excluded.commonalities_summary,
             source_client_slugs = excluded.source_client_slugs,
             refreshed_at = now(),
             summary_embedding = null""",
        (niche,
         json.dumps(result["top_pains"]),
         json.dumps(result["shared_lingo"]),
         json.dumps(result["dream_outcomes"]),
         json.dumps(result["winning_levers"]),
         result["commonalities_summary"],
         source_clients),
    )


def run(niche):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            pains, calls, winners = gather(cur, niche)
            if not pains and not calls and not winners:
                print(f"nothing to synthesize for '{niche}'. Is the niche spelled as stored?")
                return

            pain_clusters = pains_to_clusters(pains)
            lingo_samples = [row[3] for row in pains if row[1] == "lingo"][:30]
            winning_levers = [row[1] for row in winners if row[1]]
            source_clients = sorted({row[0] for row in pains}
                                    | {row[0] for row in calls}
                                    | {row[0] for row in winners})

            result = synthesize_with_llm(niche, pain_clusters, lingo_samples, winning_levers)
            upsert_niche_knowledge(cur, niche, result, source_clients)
        conn.commit()
        print(f"niche_knowledge refreshed for '{niche}' "
              f"({len(pain_clusters)} pain clusters, {len(source_clients)} clients).")
        print("now run: python scripts/embed.py")
    finally:
        conn.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--niche", required=True)
    args = ap.parse_args()
    run(args.niche)
