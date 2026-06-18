"""Agent A — Case Study agent.

Takes pasted case-study text (or the CASE STUDIES tab) for an EXISTING client,
splits it into separate case studies, extracts the structured fields, scores the
tier with the Scaletopia rubric, builds a stable source_ref, upserts into
case_studies (dedup on source_ref), then embeds.

The client must already exist (run onboarding_agent.py first).

Usage:
  python case_study_agent.py --client kynship \
      --file clients/kynship/case-studies.csv \
      --source-label "Kynship Master Sheet · Tab 4"
"""
import os
import sys
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from connections.supabase import get_conn, resolve_client
from connections.gemini import extract_json
from shared.writers import upsert_case_study
from shared.embed import embed_all

SYSTEM = (
    "You are a case-study analyst for a cold-outreach agency. You read messy case "
    "study notes and return STRICT JSON only. Never invent metrics; if a field is "
    "unknown, use null."
)

# The tiering rubric from the Scaletopia master sheet (Tab 5).
RUBRIC = """TIER RULES (score each case study):
- S: Transformation result + clear unique mechanism + recognizable logo/client.
- A: Any TWO of {transformation result, unique mechanism, recognizable logo}.
- B: Just revenue/results + timeframe (no transformation, weak/no mechanism).
- C: Metric-only stats (leads, CPA, ROAS, impressive views) — marketey but no revenue transformation.
- D: Metric-only with weak signals (percentages, organic impressions)."""

PROMPT = """Split the material below into SEPARATE case studies (one per real brand/result).
For each, return an object. Return STRICT JSON: {{ "case_studies": [ ... ] }} where each item is:

{{
  "subject_brand": "the brand the result is about (REQUIRED)",
  "source_url": "their website if present, else null",
  "service": "what was done, e.g. 'Facebook ads, creative'",
  "before_state": "the before situation + pains",
  "after_state": "the headline win/result (REQUIRED)",
  "notable_results": "extra impressive details, or null",
  "timeframe": "how long it took, e.g. '2 years', or null",
  "mechanism_literal": "what was actually done, plainly",
  "unique_mechanism": "the clever angle in <15 words, or null",
  "tier": "S | A | B | C | D",
  "row_hint": "a short stable label for this row, e.g. brand name or row number"
}}

{rubric}

Rules:
- Skip the rubric/instruction rows and any '{{Name}}' template placeholder rows.
- A case study MUST have subject_brand and after_state, or drop it.
- Be honest about tier — most are A/B. Only give S when all three S-criteria are clearly present.

MATERIAL:
---
{material}
---"""


def run(client, file_path, source_label):
    with open(file_path, encoding="utf-8", errors="ignore") as f:
        material = f.read()

    conn = get_conn()
    try:
        slug, niche, sub_niche = resolve_client(conn, client)

        print("extracting + tiering with Gemini ...")
        data = extract_json(PROMPT.format(rubric=RUBRIC, material=material), system=SYSTEM)
        items = data.get("case_studies", [])
        print(f"  {len(items)} case studies parsed.")

        counts = {"inserted": 0, "updated": 0, "dropped": 0}
        with conn.cursor() as cur:
            for cs in items:
                if not cs.get("subject_brand") or not cs.get("after_state"):
                    counts["dropped"] += 1
                    continue
                cs["source_ref"] = f"{source_label} · {cs.get('row_hint') or cs['subject_brand']}"
                cs.pop("row_hint", None)
                try:
                    _id, action = upsert_case_study(cur, cs, slug, niche, sub_niche)
                    counts[action] += 1
                except ValueError as e:
                    print(f"  dropped: {e}")
                    counts["dropped"] += 1
        conn.commit()
        print(f"case studies: {counts}")
        n = embed_all(conn, only_tables={"case_studies"})
        print(f"embedded {n} case-study vectors.")
    finally:
        conn.close()
    print("done.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--client", required=True, help="slug or name; must already exist")
    ap.add_argument("--file", required=True, help="case studies text/CSV file")
    ap.add_argument("--source-label", default="pasted case studies",
                    help="stable prefix for source_ref dedup, e.g. 'Kynship Master Sheet · Tab 4'")
    args = ap.parse_args()
    run(args.client, args.file, args.source_label)
