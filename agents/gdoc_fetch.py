"""gdoc_fetch.py - download public Google Docs / Drive files as text.

Your meeting docs are shared "anyone with link", so they export as plain text
with no Google auth:
  Docs:  https://docs.google.com/document/d/<ID>/export?format=txt
  Drive: https://drive.google.com/uc?export=download&id=<ID>

Reads a links file (one URL per line; non-URL lines are ignored), downloads each,
classifies the result (text / pdf / blocked), saves the text ones to --out, and
writes a manifest. Lines that aren't links (e.g. "note taker didn't work") are
skipped and counted.

Usage:
  python gdoc_fetch.py --links ../chambermedia/gdoc_links.txt \
      --out ../chambermedia/transcripts --prefix chamber_media_gdoc
"""
import os
import re
import json
import argparse

import requests

DOC_RE = re.compile(r"docs\.google\.com/document/d/([A-Za-z0-9_-]+)")
DRIVE_RE = re.compile(r"drive\.google\.com/file/d/([A-Za-z0-9_-]+)")

UA = {"User-Agent": "Mozilla/5.0 (gdoc-fetch)"}


def classify(content_bytes):
    head = content_bytes[:400].lstrip()
    if head[:4] == b"%PDF":
        return "pdf"
    low = head.lower()
    if b"<html" in low or b"servicelogin" in low or b"accounts.google" in low:
        return "blocked"
    return "text"


def fetch(url):
    r = requests.get(url, headers=UA, timeout=60, allow_redirects=True)
    r.raise_for_status()
    return r.content


def run(links_path, out_dir, prefix):
    os.makedirs(out_dir, exist_ok=True)
    lines = open(links_path, encoding="utf-8", errors="ignore").read().splitlines()

    targets = []          # (kind, id, url)
    skipped_notes = 0
    seen = set()
    for ln in lines:
        ln = ln.strip()
        m = DOC_RE.search(ln)
        d = DRIVE_RE.search(ln)
        if m:
            gid = m.group(1)
            url = f"https://docs.google.com/document/d/{gid}/export?format=txt"
            kind = "doc"
        elif d:
            gid = d.group(1)
            url = f"https://drive.google.com/uc?export=download&id={gid}"
            kind = "drive"
        else:
            if ln and not ln.startswith("http"):
                skipped_notes += 1
            continue
        if gid in seen:
            continue
        seen.add(gid)
        targets.append((kind, gid, url))

    print(f"{len(targets)} unique links found ({skipped_notes} non-link note lines skipped).")
    manifest = []
    n_text = n_pdf = n_blocked = n_err = 0
    for i, (kind, gid, url) in enumerate(targets, 1):
        name = f"{prefix}_{i:02d}"
        rec = {"index": i, "kind": kind, "id": gid, "name": name, "status": None, "bytes": 0, "file": None}
        try:
            content = fetch(url)
            cls = classify(content)
            rec["bytes"] = len(content)
            if cls == "text":
                fpath = os.path.join(out_dir, name + ".txt")
                with open(fpath, "wb") as f:
                    f.write(content)
                rec["status"] = "text"
                rec["file"] = fpath
                n_text += 1
            elif cls == "pdf":
                fpath = os.path.join(out_dir, name + ".pdf")
                with open(fpath, "wb") as f:
                    f.write(content)
                rec["status"] = "pdf (not ingested - needs extraction)"
                rec["file"] = fpath
                n_pdf += 1
            else:
                rec["status"] = "blocked (not public / needs auth)"
                n_blocked += 1
        except Exception as e:
            rec["status"] = f"error: {e}"
            n_err += 1
        print(f"  [{i:02d}] {kind:5} {gid[:18]:18} -> {rec['status']} ({rec['bytes']} b)")
        manifest.append(rec)

    mpath = os.path.join(out_dir, prefix + "_manifest.json")
    with open(mpath, "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"\ntext: {n_text} | pdf: {n_pdf} | blocked: {n_blocked} | error: {n_err}")
    print(f"manifest: {mpath}")
    print(f"text files ready to ingest: {prefix}_*.txt in {out_dir}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--links", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--prefix", default="gdoc")
    args = ap.parse_args()
    run(args.links, args.out, args.prefix)
