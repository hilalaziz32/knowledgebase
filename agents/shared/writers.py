"""Dedup-safe writers — the single insert path for agents.

Even though agents write directly to the DB, every write goes through these
functions so dedup keys and column shapes stay identical to the data-feeder
scripts. Vectors are always left NULL here; shared.embed fills them afterward.
"""
import json

PAIN_KINDS = {"pain", "lingo", "dream", "belief", "objection"}
CONFIDENCE = {"confirmed", "needs_more"}


# ---------- client_roster ----------

def upsert_client(cur, c):
    """Upsert on slug. Existing non-null values are kept if the new payload omits them."""
    if not c.get("slug") or not c.get("client"):
        raise ValueError("client needs both 'slug' and 'client' (display name)")
    cur.execute(
        """insert into client_roster (client, slug, airtable_client_id, offer, niche, sub_niche, status)
           values (%s,%s,%s,%s,%s,%s, coalesce(%s,'active'))
           on conflict (slug) do update set
             client = excluded.client,
             airtable_client_id = coalesce(excluded.airtable_client_id, client_roster.airtable_client_id),
             offer = coalesce(excluded.offer, client_roster.offer),
             niche = coalesce(excluded.niche, client_roster.niche),
             sub_niche = coalesce(excluded.sub_niche, client_roster.sub_niche)
           returning slug, niche, sub_niche""",
        (c.get("client"), c["slug"], c.get("airtable_client_id"),
         c.get("offer"), c.get("niche"), c.get("sub_niche"), c.get("status")),
    )
    return cur.fetchone()


# ---------- case_studies (dedup on source_ref) ----------

def upsert_case_study(cur, cs, slug, niche, sub_niche):
    if not cs.get("subject_brand") or not cs.get("after_state"):
        raise ValueError("case study needs both subject_brand and after_state")
    src = cs.get("source_ref")
    fields = (
        src,
        cs.get("owner_client_slug", slug),
        cs.get("subject_brand"),
        cs.get("niche", niche),
        cs.get("sub_niche", sub_niche),
        cs.get("service"),
        cs.get("before_state"),
        cs.get("after_state"),
        cs.get("notable_results"),
        cs.get("timeframe"),
        cs.get("mechanism_literal"),
        cs.get("unique_mechanism"),
        cs.get("tier", "D"),
        cs.get("source_url"),
    )
    if src:
        cur.execute("select id from case_studies where source_ref = %s", (src,))
        hit = cur.fetchone()
        if hit:
            cur.execute(
                """update case_studies set
                     owner_client_slug=%s, subject_brand=%s, niche=%s, sub_niche=%s, service=%s,
                     before_state=%s, after_state=%s, notable_results=%s, timeframe=%s,
                     mechanism_literal=%s, unique_mechanism=%s, tier=%s, source_url=%s
                   where id=%s
                   returning id""",
                fields[1:] + (hit[0],),
            )
            return cur.fetchone()[0], "updated"
    cur.execute(
        """insert into case_studies
           (source_ref, owner_client_slug, subject_brand, niche, sub_niche, service,
            before_state, after_state, notable_results, timeframe,
            mechanism_literal, unique_mechanism, tier, source_url)
           values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
           returning id""",
        fields,
    )
    return cur.fetchone()[0], "inserted"


# ---------- master_sheet_pains (dedup on slug+text, upgrade trust) ----------

def upsert_pain(cur, p, slug, niche, sub_niche):
    text = (p.get("text") or "").strip()
    if not text:
        raise ValueError("pain has empty text")
    kind = p.get("kind")
    if kind not in PAIN_KINDS:
        raise ValueError(f"pain.kind '{kind}' not in {sorted(PAIN_KINDS)}")
    conf = p.get("confidence", "needs_more")
    if conf not in CONFIDENCE:
        raise ValueError(f"pain.confidence '{conf}' not in {sorted(CONFIDENCE)}")

    cur.execute(
        "select id, confidence from master_sheet_pains where client_slug=%s and item_text=%s",
        (slug, text),
    )
    hit = cur.fetchone()
    if hit:
        if hit[1] == "needs_more" and conf == "confirmed":
            cur.execute("update master_sheet_pains set confidence='confirmed' where id=%s", (hit[0],))
            return "upgraded"
        return "skipped"
    cur.execute(
        """insert into master_sheet_pains
           (client_slug, niche, sub_niche, kind, persona, item_text, confidence, source)
           values (%s,%s,%s,%s,%s,%s,%s,%s)""",
        (slug, p.get("niche", niche), p.get("sub_niche", sub_niche), kind,
         p.get("persona"), text, conf, p.get("source")),
    )
    return "inserted"


# ---------- client_calls (dedup on source_call_id) + call_chunks ----------

def upsert_call(cur, slug, source_call_id, transcript, title, call_date, participants, provider, rechunk):
    """Returns (call_id, existed). Deletes old chunks when rechunking."""
    cur.execute("select id from client_calls where source_call_id = %s", (source_call_id,))
    existing = cur.fetchone()
    if existing and not rechunk:
        return existing[0], True
    if existing:
        call_id = existing[0]
        cur.execute(
            """update client_calls set client_slug=%s, title=%s, call_date=%s, source=%s,
                   participants=%s, raw_transcript=%s where id=%s""",
            (slug, title, call_date, provider, participants, transcript, call_id),
        )
        cur.execute("delete from call_chunks where call_id = %s", (call_id,))
        return call_id, True
    cur.execute(
        """insert into client_calls
           (client_slug, title, call_date, source, source_call_id, participants, raw_transcript)
           values (%s,%s,%s,%s,%s,%s,%s) returning id""",
        (slug, title, call_date, provider, source_call_id, participants, transcript),
    )
    return cur.fetchone()[0], False


def insert_chunks(cur, call_id, slug, niche, chunks):
    for i, chunk in enumerate(chunks):
        cur.execute(
            """insert into call_chunks (call_id, client_slug, niche, chunk_index, chunk_text, embedding)
               values (%s,%s,%s,%s,%s,null)""",
            (call_id, slug, niche, i, chunk),
        )
    return len(chunks)


# ---------- copies + copy_components ----------

COPY_FIELDS = [
    "airtable_copy_id", "origin", "client_slug", "campaign_id", "case_study_id",
    "niche", "sub_niche", "persona", "sophistication", "channel", "t1", "t2",
    "lever", "pattern", "what_carries", "proof_framing", "unique_mechanism",
    "pattern_interrupt", "cta", "relevance_type", "status", "model_score",
    "why_it_worked", "why_it_failed",
]
COMPONENT_TYPES = {"disarmer", "identity", "case_line", "unique_mechanism", "relevance", "cta"}


def save_copy(cur, c):
    """Insert a copy with char counts computed and its components. Vectors NULL.
    Returns (copy_id, [component_ids]). campaign_id may be set now or linked later."""
    t1 = c.get("t1") or ""
    t2 = c.get("t2") or ""
    status = c.get("status") or "draft"

    cols = COPY_FIELDS + ["char_t1", "char_t2", "lineage"]
    vals = [c.get(k) for k in COPY_FIELDS] + [
        len(t1), len(t2),
        json.dumps(c["lineage"]) if c.get("lineage") is not None else None,
    ]
    # defaults
    vals[COPY_FIELDS.index("origin")] = c.get("origin") or "scaletopia_send"
    vals[COPY_FIELDS.index("channel")] = c.get("channel") or "sms"
    vals[COPY_FIELDS.index("status")] = status

    placeholders = ",".join(["%s"] * len(cols))
    cur.execute(
        f"insert into copies ({','.join(cols)}) values ({placeholders}) returning id", vals
    )
    copy_id = cur.fetchone()[0]

    verdict = "winner" if status == "winner" else "neutral"
    comp_ids = []
    for comp in c.get("components", []):
        ctype = comp.get("component_type")
        text = (comp.get("item_text") or "").strip()
        if not ctype or not text:
            continue
        cur.execute(
            """insert into copy_components
               (copy_id, component_type, item_text, verdict, niche, persona, lever)
               values (%s,%s,%s,%s,%s,%s,%s) returning id""",
            (copy_id, ctype, text, verdict, c.get("niche"), c.get("persona"), c.get("lever")),
        )
        comp_ids.append(cur.fetchone()[0])
    return copy_id, comp_ids


def link_copy_to_campaign(cur, copy_id, campaign_id):
    """Set a copy's campaign_id and inherit the campaign's niche/persona if missing."""
    cur.execute("select niche, persona from campaigns where id=%s", (campaign_id,))
    row = cur.fetchone()
    if not row:
        raise ValueError(f"campaign {campaign_id} not found")
    c_niche, c_persona = row
    cur.execute(
        """update copies set campaign_id=%s,
             niche=coalesce(niche,%s), persona=coalesce(persona,%s), updated_at=now()
           where id=%s""",
        (campaign_id, c_niche, c_persona, copy_id),
    )
