"""The ONE embedding path for agents.

Mirrors the data-feeder embed registry: it walks every (table, vector_col, text)
target, finds rows with a NULL vector and non-empty text, embeds them with Gemini,
and writes them back. Idempotent — safe to run repeatedly. Agents call
embed_all(conn) right after they finish writing, so a row is never left unsearchable
and the embedding model never drifts from the search side.
"""
from connections.gemini import embed_documents

# (table, vector_col, text_sql) — kept identical to data-feeder/config/embed_registry.json
REGISTRY = [
    ("call_chunks",        "embedding",                  "chunk_text"),
    ("case_studies",       "result_embedding",           "concat_ws(' ', after_state, notable_results)"),
    ("case_studies",       "unique_mechanism_embedding", "unique_mechanism"),
    ("case_studies",       "niche_embedding",            "concat_ws(' ', niche, sub_niche)"),
    ("master_sheet_pains", "embedding",                  "item_text"),
    ("copies",             "full_copy_embedding",        "concat_ws(' ', t1, t2)"),
    ("copies",             "t1_embedding",               "t1"),
    ("copies",             "unique_mechanism_embedding", "unique_mechanism"),
    ("copy_components",    "embedding",                  "item_text"),
    ("niche_knowledge",    "summary_embedding",          "commonalities_summary"),
]

BATCH = 64


def embed_all(conn, only_tables=None):
    """Fill every NULL vector with non-empty text. Returns total rows embedded."""
    total = 0
    with conn.cursor() as cur:
        for table, vec_col, text_sql in REGISTRY:
            if only_tables and table not in only_tables:
                continue
            cur.execute(
                f"""select id, {text_sql} as txt
                    from {table}
                    where {vec_col} is null
                      and {text_sql} is not null
                      and length(trim({text_sql})) > 0"""
            )
            rows = cur.fetchall()
            for i in range(0, len(rows), BATCH):
                batch = rows[i:i + BATCH]
                vectors = embed_documents([r[1] for r in batch])
                for (row_id, _txt), vec in zip(batch, vectors):
                    cur.execute(
                        f"update {table} set {vec_col} = %s where id = %s",
                        (vec, row_id),
                    )
                total += len(batch)
    conn.commit()
    return total
