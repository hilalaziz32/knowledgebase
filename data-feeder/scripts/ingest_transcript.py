"""
ingest_transcript.py - manual transcript intake.

Resolves the client, upserts the call on its source id, chunks the transcript
turn by turn, and inserts the chunks with the niche stamped on and vectors NULL.
No live webhooks: transcripts are handed in here. Run embed.py afterward.
"""
import os
import sys
import re
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from connections.supabase import get_conn, resolve_client

SPEAKER_RE = re.compile(r"^\s*([A-Z][\w .'\-]{0,40}):\s")
TARGET_TOKENS = 400
MAX_TOKENS = 512
OVERLAP_TOKENS = 50


def _tokens(text):
    return max(1, len(text) // 4)  # chars/4 heuristic


def _group_turns(text):
    """Group lines into speaker turns. A new turn starts on a 'Name:' line."""
    lines = [ln for ln in text.splitlines() if ln.strip()]
    turns = []
    current = []
    for ln in lines:
        if SPEAKER_RE.match(ln) and current:
            turns.append("\n".join(current))
            current = [ln]
        else:
            current.append(ln)
    if current:
        turns.append("\n".join(current))
    return turns


def _overlap_tail(turns):
    """Return the trailing turns whose token sum reaches the overlap budget."""
    tail = []
    total = 0
    for t in reversed(turns):
        tail.insert(0, t)
        total += _tokens(t)
        if total >= OVERLAP_TOKENS:
            break
    return tail


def chunk_transcript(text):
    turns = _group_turns(text)
    has_speakers = any(SPEAKER_RE.match(t.splitlines()[0]) for t in turns if t.splitlines())

    if not has_speakers:
        return _fixed_windows(text)

    chunks = []
    cur = []
    cur_tokens = 0
    for turn in turns:
        tt = _tokens(turn)
        if cur and cur_tokens + tt > TARGET_TOKENS:
            chunks.append("\n".join(cur))
            cur = _overlap_tail(cur)
            cur_tokens = sum(_tokens(x) for x in cur)
        cur.append(turn)
        cur_tokens += tt
        # a single huge turn still flushes so we never blow past the hard max
        if cur_tokens >= MAX_TOKENS:
            chunks.append("\n".join(cur))
            cur = _overlap_tail(cur)
            cur_tokens = sum(_tokens(x) for x in cur)
    if cur:
        chunks.append("\n".join(cur))
    return chunks


def _fixed_windows(text):
    """Fallback when there is no speaker structure: fixed char windows with overlap."""
    size = TARGET_TOKENS * 4
    overlap = OVERLAP_TOKENS * 4
    chunks = []
    start = 0
    while start < len(text):
        chunks.append(text[start:start + size])
        start += size - overlap
    return chunks


def ingest(client_name, source_call_id, transcript, title, call_date, participants, provider, rechunk):
    conn = get_conn()
    try:
        slug, niche, _sub = resolve_client(conn, client_name)

        with conn.cursor() as cur:
            cur.execute(
                "select id from client_calls where source_call_id = %s",
                (source_call_id,),
            )
            existing = cur.fetchone()

            if existing and not rechunk:
                print(f"exists: call {existing[0]} already ingested. Pass --rechunk to redo.")
                return

            if existing:
                call_id = existing[0]
                cur.execute(
                    """update client_calls
                       set client_slug=%s, title=%s, call_date=%s, source=%s,
                           participants=%s, raw_transcript=%s
                       where id=%s""",
                    (slug, title, call_date, provider, participants, transcript, call_id),
                )
                cur.execute("delete from call_chunks where call_id = %s", (call_id,))
            else:
                cur.execute(
                    """insert into client_calls
                       (client_slug, title, call_date, source, source_call_id, participants, raw_transcript)
                       values (%s,%s,%s,%s,%s,%s,%s) returning id""",
                    (slug, title, call_date, provider, source_call_id, participants, transcript),
                )
                call_id = cur.fetchone()[0]

            chunks = chunk_transcript(transcript)
            for i, chunk in enumerate(chunks):
                cur.execute(
                    """insert into call_chunks (call_id, client_slug, niche, chunk_index, chunk_text, embedding)
                       values (%s,%s,%s,%s,%s,null)""",
                    (call_id, slug, niche, i, chunk),
                )
        conn.commit()
        print(f"created: call {call_id} for {slug}, {len(chunks)} chunks. Now run: python scripts/embed.py")
    finally:
        conn.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--client", required=True)
    ap.add_argument("--source-call-id", required=True)
    ap.add_argument("--file", help="path to the transcript text file")
    ap.add_argument("--text", help="transcript text inline (use instead of --file)")
    ap.add_argument("--title", default=None)
    ap.add_argument("--date", dest="call_date", default=None)
    ap.add_argument("--participants", default=None)
    ap.add_argument("--provider", default="manual")
    ap.add_argument("--rechunk", action="store_true")
    args = ap.parse_args()

    if args.file:
        with open(args.file) as f:
            transcript = f.read()
    elif args.text:
        transcript = args.text
    else:
        raise SystemExit("provide --file or --text")

    ingest(args.client, args.source_call_id, transcript, args.title,
           args.call_date, args.participants, args.provider, args.rechunk)
