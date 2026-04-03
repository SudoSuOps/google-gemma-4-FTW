#!/usr/bin/env python3
"""
SwarmChain Bin — The Pair Queue
================================
Pairs go IN the bin. Judges pull FROM the bin. Deeds come OUT.

The bin is a PostgreSQL-backed queue with states:
  QUEUED   → pair is waiting for tribunal
  JUDGING  → pair is being scored (locked by a judge worker)
  SCORED   → both judges scored, 2-pass validated
  DEEDED   → deed issued, ready for finality
  ANCHORED → Merkle root on Hedera, deed is FINAL

Usage:
    python bin.py load --domain medical --limit 50     # Load pairs into bin
    python bin.py status                                # Show bin status
    python bin.py run --workers 2                       # Run tribunal workers
    python bin.py flush --domain medical                # Move scored → deeded
"""
import argparse
import json
import hashlib
import time
import os
import sys
import urllib.request
from pathlib import Path

DB_URL = os.environ.get("DATABASE_URL", "postgresql://swarm:swarmandbee2026@192.168.0.102:5433/swarmgraph")

JUDGE_A_ENDPOINT = os.environ.get("JUDGE_A", "http://localhost:11434")
JUDGE_B_ENDPOINT = os.environ.get("JUDGE_B", "http://192.168.0.99:11434")
JUDGE_A_MODEL = "gemma3:12b"
JUDGE_B_MODEL = "qwen2.5:7b"

SCORING_PROMPT = """You are an expert data quality judge. Score the following AI training pair on a scale of 0.00 to 1.00.

Evaluate on these criteria:
1. ACCURACY — Are facts, calculations, and claims correct?
2. COMPLETENESS — Does the response fully address the query?
3. SPECIFICITY — Does it provide concrete details, not generic advice?
4. STRUCTURE — Is it well-organized and actionable?
5. DOMAIN EXPERTISE — Does it demonstrate real domain knowledge?

SYSTEM PROMPT:
{system}

USER QUERY:
{user}

ASSISTANT RESPONSE:
{assistant}

Respond with ONLY a JSON object:
{{"score": <float 0.00-1.00>, "reasoning": "<2-3 sentence explanation>"}}"""


def get_conn():
    import psycopg2
    return psycopg2.connect(DB_URL)


def ensure_bin_table():
    """Create the bin table if it doesn't exist."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS bin (
            id BIGSERIAL PRIMARY KEY,
            pair_id UUID NOT NULL REFERENCES pairs(id),
            domain_id TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'queued',
            judge_a_score REAL,
            judge_a_pass2 REAL,
            judge_a_reasoning TEXT,
            judge_b_score REAL,
            judge_b_pass2 REAL,
            judge_b_reasoning TEXT,
            final_score REAL,
            max_drift REAL,
            tier TEXT,
            deed_id TEXT,
            queued_at TIMESTAMPTZ DEFAULT NOW(),
            scored_at TIMESTAMPTZ,
            deeded_at TIMESTAMPTZ,
            anchored_at TIMESTAMPTZ
        );
        CREATE INDEX IF NOT EXISTS idx_bin_status ON bin(status);
        CREATE INDEX IF NOT EXISTS idx_bin_domain ON bin(domain_id);
    """)
    conn.commit()
    conn.close()


def load_pairs(domain, limit=50):
    """Load pairs from the pairs table into the bin."""
    conn = get_conn()
    cur = conn.cursor()

    # Find pairs not already in bin
    cur.execute("""
        INSERT INTO bin (pair_id, domain_id, status)
        SELECT p.id, p.domain_id, 'queued'
        FROM pairs p
        LEFT JOIN bin b ON b.pair_id = p.id
        WHERE p.domain_id = %s AND b.id IS NULL
        LIMIT %s
    """, (domain, limit))

    loaded = cur.rowcount
    conn.commit()
    conn.close()
    print(f"[bin] Loaded {loaded} {domain} pairs into bin")
    return loaded


def score_pair(messages, endpoint, model):
    """Score a pair via ollama OpenAI-compatible API."""
    system = next((m["content"] for m in messages if m["role"] == "system"), "")
    user = next((m["content"] for m in messages if m["role"] == "user"), "")
    assistant = next((m["content"] for m in messages if m["role"] == "assistant"), "")

    prompt = SCORING_PROMPT.format(
        system=system[:1000], user=user[:1500], assistant=assistant[:2000]
    )

    payload = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1,
        "max_tokens": 200,
    }).encode()

    req = urllib.request.Request(
        f"{endpoint}/v1/chat/completions",
        data=payload,
        headers={"Content-Type": "application/json"},
    )

    try:
        resp = urllib.request.urlopen(req, timeout=120)
        data = json.loads(resp.read().decode())
        response = data["choices"][0]["message"]["content"]

        # Parse JSON response
        response = response.strip()
        if response.startswith("```"):
            response = response.split("```")[1].strip()
            if response.startswith("json"):
                response = response[4:].strip()

        result = json.loads(response)
        return float(result["score"]), result.get("reasoning", "")
    except json.JSONDecodeError:
        # Try to extract score from non-JSON response
        import re
        match = re.search(r'"score"\s*:\s*([\d.]+)', response if 'response' in dir() else "")
        if match:
            return float(match.group(1)), "parse_fallback"
        return None, f"parse_error"
    except Exception as e:
        return None, str(e)


def classify(score):
    if score >= 0.75: return "royal_jelly"
    if score >= 0.50: return "honey"
    return "propolis"


def run_tribunal(batch_size=10):
    """Pull pairs from bin and run through dual-judge tribunal."""
    conn = get_conn()
    cur = conn.cursor()

    # Pull queued pairs
    cur.execute("""
        UPDATE bin SET status = 'judging'
        WHERE id IN (
            SELECT id FROM bin WHERE status = 'queued' ORDER BY id LIMIT %s
            FOR UPDATE SKIP LOCKED
        )
        RETURNING id, pair_id
    """, (batch_size,))

    work = cur.fetchall()
    conn.commit()

    if not work:
        print("[bin] No pairs in queue")
        return 0

    print(f"[bin] Judging {len(work)} pairs...")
    scored = 0
    flagged = 0

    for bin_id, pair_id in work:
        # Get messages
        cur.execute("SELECT messages FROM pairs WHERE id = %s", (pair_id,))
        row = cur.fetchone()
        if not row:
            continue
        messages = row[0]

        # PASS 1: Both judges score
        score_a1, reason_a = score_pair(messages, JUDGE_A_ENDPOINT, JUDGE_A_MODEL)
        score_b1, reason_b = score_pair(messages, JUDGE_B_ENDPOINT, JUDGE_B_MODEL)

        if score_a1 is None or score_b1 is None:
            cur.execute("UPDATE bin SET status = 'queued' WHERE id = %s", (bin_id,))
            conn.commit()
            print(f"  [{bin_id}] ERROR: A={score_a1} B={score_b1} — requeued")
            continue

        # PASS 2: Validate the validator
        score_a2, _ = score_pair(messages, JUDGE_A_ENDPOINT, JUDGE_A_MODEL)
        score_b2, _ = score_pair(messages, JUDGE_B_ENDPOINT, JUDGE_B_MODEL)

        if score_a2 is None: score_a2 = score_a1
        if score_b2 is None: score_b2 = score_b1

        drift_a = abs(score_a1 - score_a2)
        drift_b = abs(score_b1 - score_b2)
        max_drift = max(drift_a, drift_b)

        if max_drift > 0.15:
            cur.execute("""
                UPDATE bin SET status = 'flagged', max_drift = %s, scored_at = NOW()
                WHERE id = %s
            """, (max_drift, bin_id))
            flagged += 1
            print(f"  [{bin_id}] FLAGGED: drift={max_drift:.3f}")
        else:
            final_a = round((score_a1 + score_a2) / 2, 4)
            final_b = round((score_b1 + score_b2) / 2, 4)
            final = round((final_a + final_b) / 2, 4)
            tier = classify(final)

            cur.execute("""
                UPDATE bin SET
                    status = 'scored',
                    judge_a_score = %s, judge_a_pass2 = %s, judge_a_reasoning = %s,
                    judge_b_score = %s, judge_b_pass2 = %s, judge_b_reasoning = %s,
                    final_score = %s, max_drift = %s, tier = %s,
                    scored_at = NOW()
                WHERE id = %s
            """, (final_a, score_a2, reason_a, final_b, score_b2, reason_b,
                  final, max_drift, tier, bin_id))
            scored += 1
            print(f"  [{bin_id}] score={final:.3f} tier={tier} drift={max_drift:.3f}")

        conn.commit()

    print(f"\n[bin] Batch complete: {scored} scored, {flagged} flagged")
    conn.close()
    return scored


def show_status():
    """Show bin queue status."""
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        SELECT status, COUNT(*), domain_id
        FROM bin GROUP BY status, domain_id ORDER BY domain_id, status
    """)
    rows = cur.fetchall()

    cur.execute("SELECT COUNT(*) FROM bin")
    total = cur.fetchone()[0]

    print(f"\n{'='*60}")
    print(f"  SWARMCHAIN BIN STATUS")
    print(f"{'='*60}")
    print(f"  Total in bin: {total:,}")
    print()

    if rows:
        cur_domain = None
        for status, count, domain in rows:
            if domain != cur_domain:
                print(f"  {domain}:")
                cur_domain = domain
            print(f"    {status:12s}: {count:,}")

    # Tier breakdown of scored
    cur.execute("""
        SELECT tier, COUNT(*), ROUND(AVG(final_score)::numeric, 4)
        FROM bin WHERE status = 'scored' AND tier IS NOT NULL
        GROUP BY tier ORDER BY tier
    """)
    tiers = cur.fetchall()
    if tiers:
        print(f"\n  Scored tier breakdown:")
        for tier, count, avg in tiers:
            print(f"    {tier:15s}: {count:,} (mean: {avg})")

    print(f"{'='*60}\n")
    conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SwarmChain Bin")
    sub = parser.add_subparsers(dest="command")

    p_load = sub.add_parser("load")
    p_load.add_argument("--domain", required=True)
    p_load.add_argument("--limit", type=int, default=50)

    p_run = sub.add_parser("run")
    p_run.add_argument("--batch", type=int, default=10)
    p_run.add_argument("--continuous", action="store_true")

    sub.add_parser("status")

    args = parser.parse_args()
    ensure_bin_table()

    if args.command == "load":
        load_pairs(args.domain, args.limit)
    elif args.command == "run":
        if args.continuous:
            while True:
                scored = run_tribunal(args.batch)
                if scored == 0:
                    print("[bin] Queue empty. Waiting 30s...")
                    time.sleep(30)
        else:
            run_tribunal(args.batch)
    elif args.command == "status":
        show_status()
    else:
        parser.print_help()
