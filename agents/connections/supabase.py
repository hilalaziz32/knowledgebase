"""Shared Supabase / Postgres connection and client resolution.

Same single DB path the data-feeder scripts use, so agents and scripts insert
through identical logic. pgvector adapter registered so we can write 1536-dim
vectors directly.
"""
import os
import psycopg2
from pgvector.psycopg2 import register_vector

import connections  # noqa: F401  (loads .env)


def get_conn():
    url = os.environ.get("SUPABASE_DB_URL")
    if not url:
        raise RuntimeError("SUPABASE_DB_URL is not set. Copy .env.example to .env and fill it in.")
    conn = psycopg2.connect(url)
    register_vector(conn)
    return conn


def resolve_client(conn, name_or_slug):
    """Turn a name or slug into (slug, niche, sub_niche). No fuzzy guessing.
    Order: exact slug -> case-insensitive client name -> alias."""
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
        f"unknown_client: '{name_or_slug}' is not in client_roster. Run the onboarding agent first."
    )
