"""Gemini: the ONE LLM path and the ONE embedding path.

Embeddings: gemini-embedding-001, 1536 dims, L2-normalized. This MUST match the
search side exactly or retrieval silently returns nothing. Stored content uses
RETRIEVAL_DOCUMENT, queries use RETRIEVAL_QUERY.

LLM: used for the judgment work (parse messy paste -> clean JSON). extract_json()
forces a JSON response and parses it, raising loudly on malformed output.
"""
import os
import re
import json
import math

from google import genai
from google.genai import types

import connections  # noqa: F401  (loads .env)

EMBED_MODEL = os.environ.get("GEMINI_EMBED_MODEL", "gemini-embedding-001")
LLM_MODEL = os.environ.get("GEMINI_LLM_MODEL", "gemini-2.5-flash")
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


# ---------- embeddings ----------

def _l2_normalize(vec):
    norm = math.sqrt(sum(x * x for x in vec))
    return vec if norm == 0 else [x / norm for x in vec]


def _embed(texts, task_type):
    client = _get_client()
    resp = client.models.embed_content(
        model=EMBED_MODEL,
        contents=texts,
        config=types.EmbedContentConfig(task_type=task_type, output_dimensionality=DIM),
    )
    return [_l2_normalize(e.values) for e in resp.embeddings]


def embed_documents(texts):
    """Embed stored content (chunks, copies, pains, case studies, summaries)."""
    return _embed(texts, "RETRIEVAL_DOCUMENT")


def embed_query(text):
    """Embed a single search query. Returns one 1536-dim vector."""
    return _embed([text], "RETRIEVAL_QUERY")[0]


# ---------- LLM extraction ----------

_JSON_FENCE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)


def extract_json(prompt, *, system=None):
    """Send a prompt, force JSON out, parse and return it. Raises on bad JSON."""
    client = _get_client()
    contents = prompt if system is None else f"{system}\n\n{prompt}"
    resp = client.models.generate_content(
        model=LLM_MODEL,
        contents=contents,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.2,
        ),
    )
    text = (resp.text or "").strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = _JSON_FENCE.search(text)
        if m:
            return json.loads(m.group(1))
        raise ValueError(f"LLM did not return valid JSON. Got:\n{text[:1000]}")
