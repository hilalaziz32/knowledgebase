"""
Shared Supabase / Postgres connection and client resolution.
Every script imports from here so there is exactly one DB path and one
way to turn a client name into a slug.
"""
import os
import psycopg2
from pgvector.psycopg2 import register_vector


def get_conn():
    """Open a connection to the Evergreen DB with the pgvector adapter registered."""
    url = os.environ.get("SUPABASE_DB_URL")
    if not url:
        raise RuntimeError("SUPABASE_DB_URL is not set. Copy .env.example to .env and fill it in.")
    conn = psycopg2.connect(url)
    register_vector(conn)
    return conn


def resolve_client(conn, name_or_slug):
    """
    Turn whatever the AI sent (a name or a slug) into (slug, niche, sub_niche).
    Order: exact slug -> case-insensitive client name -> alias. No fuzzy guessing.
    Raises on no match, because a campaign or call with no client is a silent corruption.
    """
    with conn.cursor() as cur:
        cur.execute(
            "select slug, niche, sub_niche from client_roster where slug = %s",
            (name_or_slug,),
        )
        row = cur.fetchone()
        if row:
            return row

        cur.execute(
            "select slug, niche, sub_niche from client_roster where lower(client) = lower(%s)",
            (name_or_slug,),
        )
        row = cur.fetchone()
        if row:
            return row

        cur.execute(
            """select cr.slug, cr.niche, cr.sub_niche
               from client_aliases a
               join client_roster cr on cr.slug = a.client_slug
               where lower(a.alias) = lower(%s)""",
            (name_or_slug,),
        )
        row = cur.fetchone()
        if row:
            return row

    raise ValueError(
        f"unknown_client: '{name_or_slug}' is not in client_roster. Add the client first."
    )
