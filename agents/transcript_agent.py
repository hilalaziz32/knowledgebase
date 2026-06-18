"""Agent C — Transcript agent.

Given a call transcript for an EXISTING client:
  1. saves the full raw transcript -> client_calls (dedup on source_call_id),
  2. chunks it turn-by-turn -> call_chunks,
  3. mines the transcript for NEW pains/lingo/objections -> master_sheet_pains
     (as needs_more, so the sheet can later upgrade them to confirmed),
  4. embeds the new chunks + pains.

Usage:
  python transcript_agent.py --client kynship --source-call-id kynship_disc_01 \
      --file clients/kynship/transcripts/discovery.txt \
      --title "Discovery" --date 2026-04-03 --provider fathom
"""
import os
import sys
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from connections.supabase import get_conn, resolve_client
from connections.gemini import extract_json
from shared.writers import upsert_call, insert_chunks, upsert_pain
from shared.chunk import chunk_transcript
from shared.embed import embed_all

SYSTEM = (
    "You analyze sales/discovery call transcripts and return STRICT JSON only. You "
    "extract only what is genuinely said; never invent. These are tentative reads, "
    "so default confidence is needs_more."
)

MINE_PROMPT = """Read this call transcript and pull out the buyer's pains, distinctive
lingo, dreams, mistaken beliefs, and objections. Return STRICT JSON:

{{
  "pains": [
    {{
      "kind": "pain | lingo | dream | belief | objection",
      "text": "in the speaker's own words, concise",
      "persona": "the speaker's role if clear, else null",
      "confidence": "needs_more"
    }}
  ]
}}

Rules:
- Only include items actually expressed in the call. One idea per item.
- Always set confidence to needs_more (a transcript is evidence, not the master sheet).

TRANSCRIPT:
---
{transcript}
---"""


def run(client, source_call_id, file_path, text, title, call_date, participants, provider, rechunk, mine):
    if file_path:
        with open(file_path, encoding="utf-8", errors="ignore") as f:
            transcript = f.read()
    elif text:
        transcript = text
    else:
        raise SystemExit("provide --file or --text")

    conn = get_conn()
    try:
        slug, niche, _sub = resolve_client(conn, client)

        with conn.cursor() as cur:
            call_id, existed = upsert_call(cur, slug, source_call_id, transcript, title,
                                           call_date, participants, provider, rechunk)
            if existed and not rechunk:
                print(f"call {call_id} already ingested. Pass --rechunk to redo.")
                return
            chunks = chunk_transcript(transcript)
            n_chunks = insert_chunks(cur, call_id, slug, niche, chunks)
        conn.commit()
        print(f"call {call_id} for {slug}: {n_chunks} chunks.")

        if mine:
            print("mining pains with Gemini ...")
            data = extract_json(MINE_PROMPT.format(transcript=transcript), system=SYSTEM)
            pains = data.get("pains", [])
            counts = {"inserted": 0, "upgraded": 0, "skipped": 0}
            with conn.cursor() as cur:
                for p in pains:
                    p["source"] = f"call {source_call_id}"
                    try:
                        counts[upsert_pain(cur, p, slug, niche, _sub)] += 1
                    except ValueError as e:
                        print(f"  skipped a pain: {e}")
            conn.commit()
            print(f"mined pains: {counts}")

        n = embed_all(conn, only_tables={"call_chunks", "master_sheet_pains"})
        print(f"embedded {n} rows.")
    finally:
        conn.close()
    print("done.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--client", required=True)
    ap.add_argument("--source-call-id", required=True)
    ap.add_argument("--file")
    ap.add_argument("--text")
    ap.add_argument("--title", default=None)
    ap.add_argument("--date", dest="call_date", default=None)
    ap.add_argument("--participants", default=None)
    ap.add_argument("--provider", default="manual")
    ap.add_argument("--rechunk", action="store_true")
    ap.add_argument("--no-mine", dest="mine", action="store_false", help="skip pain mining")
    args = ap.parse_args()
    run(args.client, args.source_call_id, args.file, args.text, args.title,
        args.call_date, args.participants, args.provider, args.rechunk, args.mine)
