"""
embed.py - the one embedding path.

Walks config/embed_registry.json. For each (table, vector_col, text_sql),
finds rows where the vector is NULL and the text is non-empty, embeds them in
batches, and writes the vectors back. Incremental and idempotent: run it after
any write, run it twice, it does no harm and only fills what is missing.
"""
import os
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from connections.supabase import get_conn
from connections.gemini import embed_documents

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REGISTRY = os.path.join(ROOT, "config", "embed_registry.json")
BATCH = 100


def run():
    with open(REGISTRY) as f:
        registry = json.load(f)

    conn = get_conn()
    totals = {}
    try:
        for entry in registry:
            table = entry["table"]
            vcol = entry["vector_col"]
            tsql = entry["text_sql"]
            key = f"{table}.{vcol}"
            totals[key] = 0

            while True:
                with conn.cursor() as cur:
                    cur.execute(
                        f"""select id, {tsql} as txt
                            from {table}
                            where {vcol} is null
                              and coalesce(trim({tsql}), '') <> ''
                            order by id
                            limit {BATCH}"""
                    )
                    rows = cur.fetchall()

                if not rows:
                    break

                ids = [r[0] for r in rows]
                texts = [r[1] for r in rows]
                vectors = embed_documents(texts)

                with conn.cursor() as cur:
                    for row_id, vec in zip(ids, vectors):
                        cur.execute(
                            f"update {table} set {vcol} = %s where id = %s",
                            (vec, row_id),
                        )
                conn.commit()
                totals[key] += len(rows)

                if len(rows) < BATCH:
                    break
    finally:
        conn.close()

    print("embedded:")
    for key, n in totals.items():
        print(f"  {key}: {n}")


if __name__ == "__main__":
    run()
