#!/usr/bin/env python3
"""
SwarmChain Deed Writer — Base Model Writes Every Deed
======================================================
The deed is NOT metadata. The deed is a Q&A pair written by a base model.
The base model evaluates the pair and writes the formal deed with:
  - VERDICT (pass/fail)
  - TOTAL_SCORE
  - CLASSIFICATION (royal-jelly / honey / propolis)
  - REASONING (why this score, what's good, what's wrong)

The deed itself becomes a training pair. The system validates itself.

Protocol:
  1. Base model (gemma 2B) reads the original pair
  2. Base model writes the deed (verdict + reasoning)
  3. Deed is stored as a Q&A pair
  4. Deed goes into the graph
  5. Batch gets Merkled and anchored

Usage:
    python deed_writer.py --input scored_bin --output domains/medical/deeds/ --limit 100
    python deed_writer.py --input scored_bin --output domains/medical/deeds/ --continuous
"""
import argparse
import json
import time
import os
import urllib.request
import hashlib

from swarm_config import cfg

DB_URL = cfg.database_url
DEED_WRITER_ENDPOINT = os.environ.get("DEED_WRITER", "http://localhost:11434")
DEED_WRITER_MODEL = os.environ.get("DEED_WRITER_MODEL", cfg.deed_writer_model)
SCALE_A_MODEL = cfg.scale_a_model
SCALE_B_MODEL = cfg.scale_b_model

# Standing rule enforced by swarm_config
if DEED_WRITER_MODEL not in cfg.valid_deed_writers:
    print(f"[FATAL] Deed writer model '{DEED_WRITER_MODEL}' not in approved list: {cfg.valid_deed_writers}")
    print("[FATAL] Standing rule: NEVER use models smaller than 12B for deed writing.")
    raise SystemExit(1)

DEED_SYSTEM_PROMPT = """You are a SwarmTitle deed writer. You are a base model — unmodified, deterministic.

Your job is to evaluate an AI training pair and write a formal title deed.

You will receive:
- The SYSTEM prompt of the pair
- The USER query
- The ASSISTANT response
- The tribunal scores from two independent judges

You must write a deed with:
1. VERDICT: PASS or FAIL (does this pair meet quality standards?)
2. TOTAL_SCORE: The average of both judge scores (0-100 scale)
3. CLASSIFICATION: royal-jelly (>=75), honey (50-74), or propolis (<50)
4. REASONING: 2-4 sentences explaining why this score. What's strong? What's weak? Any factual errors? Is the response complete and actionable?

Be honest. Be specific. Cite actual content from the pair in your reasoning.
Do NOT inflate scores. Do NOT be vague. The deed is a legal document."""

DEED_USER_TEMPLATE = """Write the title deed for this training pair.

=== ORIGINAL PAIR ===

SYSTEM: {system}

USER: {user}

ASSISTANT: {assistant}

=== TRIBUNAL SCORES ===

Scale A ({judge_a_model}): {judge_a_score}
Scale B ({judge_b_model}): {judge_b_score}
Average: {final_score}

=== WRITE THE DEED ===

Format your response EXACTLY as:
VERDICT: [PASS or FAIL]
TOTAL_SCORE: [0-100]
CLASSIFICATION: [royal-jelly or honey or propolis]
REASONING: [2-4 sentences citing specific content from the pair]

/no_think"""


def write_deed(pair_messages, scale_a_weight, scale_b_weight, consensus_weight,
               judge_a_model=None, judge_b_model=None):
    """Have the base model write the deed for a weighed pair."""

    system = next((m["content"] for m in pair_messages if m["role"] == "system"), "")
    user = next((m["content"] for m in pair_messages if m["role"] == "user"), "")
    assistant = next((m["content"] for m in pair_messages if m["role"] == "assistant"), "")

    deed_prompt = DEED_USER_TEMPLATE.format(
        system=system[:1500],
        user=user[:2000],
        assistant=assistant[:3000],
        judge_a_model=judge_a_model or SCALE_A_MODEL,
        judge_b_model=judge_b_model or SCALE_B_MODEL,
        judge_a_score=f"{scale_a_weight:.2f}",
        judge_b_score=f"{scale_b_weight:.2f}",
        final_score=f"{consensus_weight:.2f}",
    )

    payload = json.dumps({
        "model": DEED_WRITER_MODEL,
        "messages": [
            {"role": "system", "content": DEED_SYSTEM_PROMPT},
            {"role": "user", "content": deed_prompt},
        ],
        "stream": False,
        "options": {"temperature": 0.1, "num_predict": 400},
    }).encode()

    req = urllib.request.Request(
        f"{DEED_WRITER_ENDPOINT}/api/chat",
        data=payload,
        headers={"Content-Type": "application/json"},
    )

    resp = urllib.request.urlopen(req, timeout=120)
    data = json.loads(resp.read().decode())
    deed_text = data.get("message", {}).get("content", "")

    # Parse the deed
    deed = parse_deed_text(deed_text, final_score)

    # The deed itself is a Q&A pair
    deed_pair = {
        "messages": [
            {"role": "system", "content": DEED_SYSTEM_PROMPT},
            {"role": "user", "content": deed_prompt},
            {"role": "assistant", "content": deed_text},
        ],
    }

    return deed, deed_pair, deed_text


def parse_deed_text(text, fallback_score):
    """Parse the model's deed output into structured data."""
    lines = text.strip().split("\n")
    verdict = "FAIL"
    total_score = int(fallback_score * 100)
    classification = "propolis"
    reasoning = ""

    for line in lines:
        line = line.strip()
        if line.upper().startswith("VERDICT:"):
            v = line.split(":", 1)[1].strip().upper()
            verdict = "PASS" if "PASS" in v else "FAIL"
        elif line.upper().startswith("TOTAL_SCORE:"):
            try:
                total_score = int(float(line.split(":", 1)[1].strip()))
            except ValueError:
                pass
        elif line.upper().startswith("CLASSIFICATION:"):
            c = line.split(":", 1)[1].strip().lower().replace(" ", "-")
            if "royal" in c or "jelly" in c:
                classification = "royal-jelly"
            elif "honey" in c:
                classification = "honey"
            else:
                classification = "propolis"
        elif line.upper().startswith("REASONING:"):
            reasoning = line.split(":", 1)[1].strip()

    # Capture any remaining lines as reasoning continuation
    in_reasoning = False
    for line in lines:
        if line.upper().startswith("REASONING:"):
            in_reasoning = True
            continue
        if in_reasoning and line.strip():
            reasoning += " " + line.strip()

    return {
        "verdict": verdict,
        "score": total_score,
        "classification": classification,
        "judge_reasoning": f"VERDICT: {verdict}\nTOTAL_SCORE: {total_score}\nCLASSIFICATION: {classification}\nREASONING: {reasoning}",
    }


def run_deed_writer(output_dir, limit=None, continuous=False):
    """Pull scored pairs from bin and write deeds with the base model."""
    import psycopg2

    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()

    os.makedirs(output_dir, exist_ok=True)
    deed_file = os.path.join(output_dir, "deeds_written.jsonl")
    pair_file = os.path.join(output_dir, "deed_pairs.jsonl")

    total_written = 0

    while True:
        # Pull scored pairs that haven't been deeded yet
        cur.execute("""
            SELECT b.id, b.pair_id, b.judge_a_score, b.judge_b_score,
                   b.final_score, b.tier, b.judge_a_reasoning, b.judge_b_reasoning,
                   p.messages, p.fingerprint, b.scored_at, b.domain_id
            FROM bin b
            JOIN pairs p ON p.id = b.pair_id
            WHERE b.status = 'scored' AND b.deed_id IS NULL AND b.final_score > 0
            ORDER BY b.id
            LIMIT %s
        """, (limit or 50,))

        rows = cur.fetchall()
        if not rows:
            if continuous:
                print("[deed-writer] Queue empty. Waiting 30s...")
                time.sleep(30)
                continue
            else:
                break

        print(f"[deed-writer] Writing {len(rows)} deeds with {DEED_WRITER_MODEL}...")

        for row in rows:
            bin_id, pair_id, ja_score, jb_score, final_score, tier, ja_reason, jb_reason, messages, fingerprint, scored_at, domain_id = row
            block_id = f"SB-2026-0403-{bin_id:05d}"

            try:
                deed, deed_pair, deed_text = write_deed(
                    messages,
                    float(ja_score), float(jb_score), float(final_score),
                )

                # Full deed record
                deed_record = {
                    "block_id": block_id,
                    "pair_index": bin_id,
                    "domain": domain_id,
                    "status": "verified",
                    "verdict": deed["verdict"],
                    "score": deed["score"],
                    "classification": deed["classification"],
                    "judge_reasoning": deed["judge_reasoning"],
                    "ledger_record": {
                        "scale_a": {"model": SCALE_A_MODEL, "weight": float(ja_score)},
                        "scale_b": {"model": SCALE_B_MODEL, "weight": float(jb_score)},
                        "final_score": float(final_score),
                        "tier": tier,
                        "deed_writer": DEED_WRITER_MODEL,
                        "permit": "PRM-2026-0403-001",
                    },
                    "energy_ms": None,
                    "sealed_at": scored_at.isoformat() if scored_at else time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "fingerprint": fingerprint,
                }

                # Write deed record
                with open(deed_file, "a") as f:
                    f.write(json.dumps(deed_record) + "\n")

                # Write deed pair (the Q&A pair that IS the deed)
                with open(pair_file, "a") as f:
                    f.write(json.dumps(deed_pair) + "\n")

                # Mark as deeded in bin
                cur.execute(
                    "UPDATE bin SET deed_id = %s, deeded_at = NOW() WHERE id = %s",
                    (block_id, bin_id)
                )
                conn.commit()

                total_written += 1
                if total_written % 10 == 0:
                    print(f"  [{total_written}] {block_id} | {deed['verdict']} | {deed['score']} | {deed['classification']}")

            except Exception as e:
                print(f"  ERROR [{bin_id}]: {e}")
                continue

        if not continuous:
            break

    print(f"\n[deed-writer] Complete: {total_written:,} deeds written by {DEED_WRITER_MODEL}")
    print(f"  Deed records: {deed_file}")
    print(f"  Deed pairs:   {pair_file}")
    conn.close()
    return total_written


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SwarmChain Deed Writer")
    parser.add_argument("--output", default="domains/medical/deeds/", help="Output directory")
    parser.add_argument("--limit", type=int, help="Limit deeds to write per batch")
    parser.add_argument("--continuous", action="store_true", help="Run continuously")
    parser.add_argument("--model", default=None, help="Deed writer model (overrides DEED_WRITER_MODEL env)")
    args = parser.parse_args()

    if args.model:
        DEED_WRITER_MODEL = args.model
    run_deed_writer(args.output, args.limit, args.continuous)
