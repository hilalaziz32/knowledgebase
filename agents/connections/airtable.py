"""Airtable read access — used to confirm a client record and to pull campaigns /
copy / metrics by client id. We READ from Airtable; n8n is what mirrors campaigns
and metrics INTO the DB. These helpers are for lookup and verification.
"""
import os

import requests

import connections  # noqa: F401  (loads .env)

_API = "https://api.airtable.com/v0"


# The Operations & Data Analytics base holds Clients / Campaigns / Copy / stats.
DEFAULT_BASE_ID = "appP3VJXaEqNopR1l"


def _headers():
    # Accept either AIRTABLE_API_KEY (agents/.env) or AIRTABLE (repo-root .env).
    key = os.environ.get("AIRTABLE_API_KEY") or os.environ.get("AIRTABLE")
    if not key:
        raise RuntimeError("No Airtable token. Set AIRTABLE_API_KEY in agents/.env or AIRTABLE in the repo-root .env.")
    return {"Authorization": f"Bearer {key}"}


def _base_id():
    return os.environ.get("AIRTABLE_BASE_ID") or DEFAULT_BASE_ID


def get_record(table, record_id):
    """Fetch a single Airtable record by its rec... id. Returns the fields dict."""
    url = f"{_API}/{_base_id()}/{table}/{record_id}"
    r = requests.get(url, headers=_headers(), timeout=30)
    r.raise_for_status()
    return r.json().get("fields", {})


def list_records(table, *, formula=None, max_records=None):
    """List records, optionally filtered by a filterByFormula. Returns list of {id, fields}."""
    url = f"{_API}/{_base_id()}/{table}"
    params = {}
    if formula:
        params["filterByFormula"] = formula
    if max_records:
        params["maxRecords"] = max_records
    out = []
    while True:
        r = requests.get(url, headers=_headers(), params=params, timeout=30)
        r.raise_for_status()
        data = r.json()
        out.extend({"id": rec["id"], "fields": rec.get("fields", {})} for rec in data.get("records", []))
        offset = data.get("offset")
        if not offset:
            break
        params["offset"] = offset
    return out
