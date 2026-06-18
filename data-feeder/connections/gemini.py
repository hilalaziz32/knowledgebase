"""
The one embedding path. Both embed.py (stored content) and search.py (queries)
call this, so the model, dimension, and normalization never drift.

Standard: gemini-embedding-001, 1536 dims, L2-normalized.
Stored content uses RETRIEVAL_DOCUMENT, query text uses RETRIEVAL_QUERY.
"""
import os
import math

from google import genai
from google.genai import types

MODEL = "gemini-embedding-001"
DIM = 1536

_client = None


def _get_client():
    global _client
    if _client is None:
        key = os.environ.get("GEMINI_API_KEY")
        if not key:
            raise RuntimeError("GEMINI_API_KEY is not set. Copy .env.example to .env and fill it in.")
        _client = genai.Client(api_key=key)
    return _client


def _l2_normalize(vec):
    norm = math.sqrt(sum(x * x for x in vec))
    if norm == 0:
        return vec
    return [x / norm for x in vec]


def embed_documents(texts):
    """Embed stored content (call chunks, copies, pains, case studies, summaries)."""
    return _embed(texts, "RETRIEVAL_DOCUMENT")


def embed_query(text):
    """Embed a single search query. Returns one 1536-dim vector."""
    return _embed([text], "RETRIEVAL_QUERY")[0]


def _embed(texts, task_type):
    client = _get_client()
    resp = client.models.embed_content(
        model=MODEL,
        contents=texts,
        config=types.EmbedContentConfig(
            task_type=task_type,
            output_dimensionality=DIM,
        ),
    )
    # The reduced (non-3072) output is not pre-normalized, so we normalize here.
    return [_l2_normalize(e.values) for e in resp.embeddings]
