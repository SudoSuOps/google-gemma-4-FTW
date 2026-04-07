#!/usr/bin/env python3
"""
SwarmChain Deed Recorder — The County Recorder's Office
=======================================================
Always-on edge service that files tribunal output into the finality pipeline.

The scale weighs. The recorder DEEDS. The deed IS the weight certificate.

Pipeline:
  1. Poll bin table for weighed pairs without deeds filed
  2. Create formal deed record (weight certificate) in deeds table
  3. Write deed JSONL to NAS holding folder (/mnt/swarm/datasets/{domain}/deeds/)
  4. Batch every 50 deeds → Merkle tree → batches table (block sealed)
  5. Update bin status to 'deeded'
  6. Log everything — no silent failures

Weight Classes:
  Class A (Royal Jelly):  weight >= 0.85 — premium, harvestable
  Class B (Honey):        weight 0.70-0.84 — value-add
  Class C (Propolis):     weight < 0.70 — composted

Designed for edge hardware (50W, no GPU). Runs 24/7 on zima-2.

Usage:
    DATABASE_URL="postgresql://..." python3 deed_recorder.py
    DATABASE_URL="postgresql://..." python3 deed_recorder.py --batch-size 50 --poll 30
"""
import argparse
import hashlib
import json
import logging
import os
import signal
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [recorder] %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("deed_recorder")

from swarm_config import cfg as swarm_cfg

DB_URL = swarm_cfg.database_url
NAS_BASE = Path(os.environ.get("NAS_DEEDS_PATH", "/mnt/swarm/datasets"))
HEDERA_TOPIC = "0.0.10291838"


def get_scale_id(domain, scale="a"):
    """Get the scale model ID for a domain from swarm.yaml."""
    a_model, b_model = swarm_cfg.get_scales(domain)
    return a_model if scale == "a" else b_model

# Graceful shutdown
_running = True
def _shutdown(sig, frame):
    global _running
    log.info("Shutdown signal received — finishing current batch...")
    _running = False
signal.signal(signal.SIGTERM, _shutdown)
signal.signal(signal.SIGINT, _shutdown)


def sha256(data: str) -> str:
    return hashlib.sha256(data.encode()).hexdigest()


def get_conn():
    import psycopg2
    if not DB_URL:
        log.error("DATABASE_URL not set — cannot connect")
        sys.exit(1)
    conn = psycopg2.connect(DB_URL, connect_timeout=10)
    conn.autocommit = False
    return conn


def poll_scored(conn, limit=100) -> list[dict]:
    """Find scored bin entries that haven't been filed as deeds yet."""
    cur = conn.cursor()
    cur.execute("""
        SELECT b.id, b.pair_id, b.domain_id, b.deed_id,
               b.judge_a_score, b.judge_a_pass2, b.judge_a_reasoning,
               b.judge_b_score, b.judge_b_pass2, b.judge_b_reasoning,
               b.final_score, b.max_drift, b.tier, b.scored_at,
               p.fingerprint, p.char_count,
               b.judge_a_accuracy, b.judge_a_completeness, b.judge_a_specificity,
               b.judge_a_structure, b.judge_a_domain_expertise,
               b.judge_b_accuracy, b.judge_b_completeness, b.judge_b_specificity,
               b.judge_b_structure, b.judge_b_domain_expertise
        FROM bin b
        JOIN pairs p ON p.id = b.pair_id
        WHERE b.status = 'scored'
          AND NOT EXISTS (SELECT 1 FROM deeds d WHERE d.id = b.deed_id)
        ORDER BY b.id
        LIMIT %s
    """, (limit,))
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def record_deed(conn, entry: dict) -> bool:
    """Insert a formal deed record into the deeds table."""
    cur = conn.cursor()

    deed_id = entry["deed_id"]
    if not deed_id:
        deed_id = f"SB-{datetime.now(timezone.utc).strftime('%Y-%m%d')}-{entry['id']:06d}"

    # DB CHECK constraint requires underscores: royal_jelly, honey, propolis
    # Display layer normalizes to hyphens — DB stores canonical form
    tier = (entry["tier"] or "propolis").replace("-", "_")
    if tier == "royal_jelly":
        tier_threshold = ">= 0.85"
    elif tier == "honey":
        tier_threshold = "0.70-0.84"
    else:
        tier_threshold = "< 0.70"

    sealed_at = entry.get("scored_at") or datetime.now(timezone.utc)

    try:
        cur.execute("""
            INSERT INTO deeds (
                id, pair_id, domain_id,
                judge_a_id, judge_a_score, judge_a_pass1, judge_a_pass2, judge_a_drift, judge_a_reasoning,
                judge_a_accuracy, judge_a_completeness, judge_a_specificity, judge_a_structure, judge_a_domain_expertise,
                judge_b_id, judge_b_score, judge_b_pass1, judge_b_pass2, judge_b_drift, judge_b_reasoning,
                judge_b_accuracy, judge_b_completeness, judge_b_specificity, judge_b_structure, judge_b_domain_expertise,
                final_score, max_drift, validated,
                tier, tier_threshold, sealed_at
            ) VALUES (
                %s, %s, %s,
                %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s, %s,
                %s, %s, %s
            )
            ON CONFLICT (id) DO NOTHING
        """, (
            deed_id, entry["pair_id"], entry["domain_id"],
            get_scale_id(entry["domain_id"], "a"), entry["judge_a_score"], entry["judge_a_score"], entry.get("judge_a_pass2"),
            abs((entry["judge_a_score"] or 0) - (entry.get("judge_a_pass2") or entry["judge_a_score"] or 0)),
            entry.get("judge_a_reasoning"),
            entry.get("judge_a_accuracy"), entry.get("judge_a_completeness"), entry.get("judge_a_specificity"),
            entry.get("judge_a_structure"), entry.get("judge_a_domain_expertise"),
            get_scale_id(entry["domain_id"], "b"), entry["judge_b_score"], entry["judge_b_score"], entry.get("judge_b_pass2"),
            abs((entry["judge_b_score"] or 0) - (entry.get("judge_b_pass2") or entry["judge_b_score"] or 0)),
            entry.get("judge_b_reasoning"),
            entry.get("judge_b_accuracy"), entry.get("judge_b_completeness"), entry.get("judge_b_specificity"),
            entry.get("judge_b_structure"), entry.get("judge_b_domain_expertise"),
            entry["final_score"], entry.get("max_drift"), True,
            tier, tier_threshold, sealed_at,
        ))

        # Update bin status
        cur.execute("""
            UPDATE bin SET status = 'deeded', deeded_at = NOW(), deed_id = %s
            WHERE id = %s
        """, (deed_id, entry["id"]))

        return True
    except Exception as e:
        log.error("Failed to record deed %s: %s", deed_id, e)
        conn.rollback()
        return False


def file_to_nas(entry: dict, deed_id: str) -> bool:
    """Write deed JSONL to NAS holding folder."""
    domain = entry["domain_id"]
    tier = (entry["tier"] or "propolis").replace("_", "-")

    # Create domain deed directory
    deed_dir = NAS_BASE / domain / "deeds"
    deed_dir.mkdir(parents=True, exist_ok=True)

    # Also create tier-specific file
    tier_file = deed_dir / f"{tier}.jsonl"

    deed_json = {
        "deed_id": deed_id,
        "pair_id": str(entry["pair_id"]),
        "domain": domain,
        "final_score": entry["final_score"],
        "tier": tier,
        "judge_a_score": entry["judge_a_score"],
        "judge_b_score": entry["judge_b_score"],
        "max_drift": entry.get("max_drift"),
        "fingerprint": entry.get("fingerprint", "")[:16],
        "sealed_at": (entry.get("scored_at") or datetime.now(timezone.utc)).isoformat(),
        "recorded_by": "deed-recorder-edge",
    }

    try:
        with open(tier_file, "a") as f:
            f.write(json.dumps(deed_json, default=str) + "\n")
        return True
    except Exception as e:
        log.error("Failed to write to NAS %s: %s", tier_file, e)
        return False


def build_merkle_batch(conn, batch_size=50) -> dict | None:
    """Check if we have enough unfiled deeds for a Merkle batch."""
    cur = conn.cursor()

    # Find deeds without a batch
    cur.execute("""
        SELECT id, pair_id, final_score, tier, sealed_at, domain_id
        FROM deeds
        WHERE batch_id IS NULL
        ORDER BY sealed_at
        LIMIT %s
    """, (batch_size,))
    deeds = cur.fetchall()

    if len(deeds) < batch_size:
        return None  # Not enough for a full batch yet

    # Build leaf hashes
    leaves = []
    deed_ids = []
    for d_id, pair_id, score, tier, sealed_at, domain in deeds:
        leaf_data = json.dumps({
            "deed_id": d_id,
            "pair_id": str(pair_id),
            "score": float(score) if score else 0,
            "tier": (tier or "").replace("_", "-"),
            "sealed_at": sealed_at.isoformat() if sealed_at else "",
        }, sort_keys=True)
        leaves.append(sha256(leaf_data))
        deed_ids.append(d_id)

    # Build Merkle tree
    current = leaves[:]
    while len(current) > 1:
        next_level = []
        for i in range(0, len(current), 2):
            left = current[i]
            right = current[i + 1] if i + 1 < len(current) else left
            next_level.append(sha256(left + right))
        current = next_level
    merkle_root = current[0]

    # Determine batch ID
    first_deed = deed_ids[0]
    last_deed = deed_ids[-1]
    batch_id = f"batch-{sha256(merkle_root)[:12]}"

    try:
        # Insert batch
        cur.execute("""
            INSERT INTO batches (id, merkle_root, leaf_count, block_range, domain_id)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (id) DO NOTHING
        """, (batch_id, merkle_root, len(leaves), f"{first_deed} — {last_deed}", deeds[0][5]))

        # Update deeds with batch info
        for i, d_id in enumerate(deed_ids):
            cur.execute("""
                UPDATE deeds SET batch_id = %s, merkle_root = %s, merkle_leaf_idx = %s
                WHERE id = %s
            """, (batch_id, merkle_root, i, d_id))

        conn.commit()
        log.info("BATCH %s: root=%s leaves=%d range=%s — %s",
                 batch_id, merkle_root[:16], len(leaves), f"{first_deed}..{last_deed}", deeds[0][5])
        return {"batch_id": batch_id, "merkle_root": merkle_root, "leaf_count": len(leaves)}

    except Exception as e:
        log.error("Failed to create batch: %s", e)
        conn.rollback()
        return None


def run(poll_interval=30, batch_size=50):
    """Main recorder loop."""
    log.info("═══ DEED RECORDER STARTING ═══")
    log.info("  DB:    %s", DB_URL[:40] + "..." if len(DB_URL) > 40 else DB_URL)
    log.info("  NAS:   %s", NAS_BASE)
    log.info("  Poll:  %ds", poll_interval)
    log.info("  Batch: %d deeds per Merkle tree", batch_size)

    # Verify NAS is mounted
    if not NAS_BASE.exists():
        log.error("NAS path %s does not exist — is it mounted?", NAS_BASE)
        sys.exit(1)

    stats = {"deeds_filed": 0, "batches_created": 0, "nas_writes": 0, "errors": 0, "started": time.time()}
    conn = None

    while _running:
        try:
            # Reconnect if needed
            if conn is None or conn.closed:
                conn = get_conn()
                log.info("Connected to PostgreSQL")

            # 1. Poll for scored entries
            entries = poll_scored(conn, limit=100)

            if entries:
                log.info("Found %d scored entries to file", len(entries))

                for entry in entries:
                    if not _running:
                        break

                    deed_id = entry.get("deed_id") or f"SB-{datetime.now(timezone.utc).strftime('%Y-%m%d')}-{entry['id']:06d}"

                    # Record to database
                    if record_deed(conn, entry):
                        stats["deeds_filed"] += 1

                        # File to NAS
                        if file_to_nas(entry, deed_id):
                            stats["nas_writes"] += 1
                        else:
                            stats["errors"] += 1
                    else:
                        stats["errors"] += 1

                conn.commit()
                log.info("Filed %d deeds (total: %d, errors: %d)",
                         len(entries), stats["deeds_filed"], stats["errors"])

            # 2. Check for Merkle batch
            batch = build_merkle_batch(conn, batch_size)
            if batch:
                stats["batches_created"] += 1

            # 3. Status heartbeat every 10 minutes
            elapsed = time.time() - stats["started"]
            if int(elapsed) % 600 < poll_interval:
                rate = stats["deeds_filed"] / max(elapsed / 3600, 0.001)
                log.info("HEARTBEAT: %d deeds filed, %d batches, %d errors, %.1f deeds/hr, uptime %.1fh",
                         stats["deeds_filed"], stats["batches_created"], stats["errors"],
                         rate, elapsed / 3600)

        except Exception as e:
            log.error("Recorder loop error: %s", e, exc_info=True)
            stats["errors"] += 1
            if conn:
                try:
                    conn.rollback()
                except Exception:
                    pass
                conn = None  # Force reconnect
            time.sleep(5)  # Back off on error
            continue

        # Sleep between polls
        time.sleep(poll_interval)

    # Cleanup
    if conn and not conn.closed:
        conn.close()

    elapsed = time.time() - stats["started"]
    log.info("═══ DEED RECORDER STOPPED ═══")
    log.info("  Deeds filed:    %d", stats["deeds_filed"])
    log.info("  Batches:        %d", stats["batches_created"])
    log.info("  NAS writes:     %d", stats["nas_writes"])
    log.info("  Errors:         %d", stats["errors"])
    log.info("  Uptime:         %.1fh", elapsed / 3600)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SwarmChain Deed Recorder — Edge Service")
    parser.add_argument("--poll", type=int, default=30, help="Poll interval in seconds")
    parser.add_argument("--batch-size", type=int, default=50, help="Deeds per Merkle batch")
    args = parser.parse_args()
    run(poll_interval=args.poll, batch_size=args.batch_size)
