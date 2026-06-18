"""Transcript chunker — turn-by-turn, ~400 tokens per chunk with 50-token overlap.
Ported from data-feeder/ingest_transcript.py so chunking stays identical.
Falls back to fixed char windows when the transcript has no speaker labels.
"""
import re

SPEAKER_RE = re.compile(r"^\s*([A-Z][\w .'\-]{0,40}):\s")
TARGET_TOKENS = 400
MAX_TOKENS = 512
OVERLAP_TOKENS = 50


def _tokens(text):
    return max(1, len(text) // 4)


def _group_turns(text):
    lines = [ln for ln in text.splitlines() if ln.strip()]
    turns, current = [], []
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
    tail, total = [], 0
    for t in reversed(turns):
        tail.insert(0, t)
        total += _tokens(t)
        if total >= OVERLAP_TOKENS:
            break
    return tail


def _fixed_windows(text):
    size = TARGET_TOKENS * 4
    overlap = OVERLAP_TOKENS * 4
    chunks, start = [], 0
    while start < len(text):
        chunks.append(text[start:start + size])
        start += size - overlap
    return chunks


def chunk_transcript(text):
    turns = _group_turns(text)
    # Require several real speaker turns before trusting speaker structure. A single
    # match (e.g. a "Call 3:" header in a timestamp transcript) is a false positive
    # and must NOT flip us into speaker mode, or the whole call collapses to 1-2 chunks.
    speaker_turns = sum(1 for t in turns if t.splitlines() and SPEAKER_RE.match(t.splitlines()[0]))
    if speaker_turns < 3:
        return _fixed_windows(text)
    chunks, cur, cur_tokens = [], [], 0
    for turn in turns:
        tt = _tokens(turn)
        if cur and cur_tokens + tt > TARGET_TOKENS:
            chunks.append("\n".join(cur))
            cur = _overlap_tail(cur)
            cur_tokens = sum(_tokens(x) for x in cur)
        cur.append(turn)
        cur_tokens += tt
        if cur_tokens >= MAX_TOKENS:
            chunks.append("\n".join(cur))
            cur = _overlap_tail(cur)
            cur_tokens = sum(_tokens(x) for x in cur)
    if cur:
        chunks.append("\n".join(cur))
    return chunks
