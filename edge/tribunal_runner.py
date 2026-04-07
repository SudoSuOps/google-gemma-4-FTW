#!/usr/bin/env python3
"""
SwarmChain Tribunal Runner — 24/7 Autonomous Weighing Pipeline
==============================================================
The tribunal is a SCALE. Two independent scales weigh each pair.
The consensus weight determines the deed. Price per pound.

Continuously loads pairs, weighs them through the dual-scale tribunal,
and lets the deed recorder handle filing. Runs forever as a systemd service.

Domain-Hash order: legal → grants → aviation → self_healing → medical → CRE
Batch size: 10 pairs per cycle (40 LLM calls per batch)
Cooldown: 5s between batches

Architecture:
  tribunal_runner (this) → loads pairs → weighs via Scale A + Scale B
  deed_recorder (edge)   → files weighed pairs into deeds + Merkle batches

Weight Classes:
  Class A (Royal Jelly):  weight >= 0.85 — premium, dense, heavy
  Class B (Honey):        weight 0.70-0.84 — solid, value-add
  Class C (Propolis):     weight < 0.70 — composted, feeds the genome

Usage:
    DATABASE_URL="postgresql://..." \
    JUDGE_A="http://localhost:11434" \
    JUDGE_B="http://192.168.0.99:11434" \
    python3 tribunal_runner.py
"""
import hashlib
import json
import logging
import os
import re
import signal
import sys
import time
import urllib.request
from datetime import datetime, timezone

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [tribunal] %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("tribunal")

from swarm_config import cfg as swarm_cfg

DB_URL = swarm_cfg.database_url
BATCH_SIZE = int(os.environ.get("BATCH_SIZE", str(swarm_cfg.tribunal_batch_size)))
COOLDOWN = int(os.environ.get("COOLDOWN", str(swarm_cfg.drift_threshold)))  # TODO: add cooldown to swarm.yaml

# Domain scoring order — configurable via env, default smallest first
DOMAIN_ORDER = os.environ.get("DOMAIN_ORDER", "legal,grants,aviation,self_healing,medical,cre,clawhash,agenthash").split(",")

# ── SCALE CONFIG FROM swarm.yaml ──
LOCAL = "http://localhost:11434"
SCALE_A_ENDPOINT = os.environ.get("SCALE_A", LOCAL)
SCALE_B_ENDPOINT = os.environ.get("SCALE_B", LOCAL)


def get_scales(domain):
    """Get scale A/B config for a domain from swarm.yaml."""
    a_model, b_model = swarm_cfg.get_scales(domain)
    swarm_cfg.validate_scale(a_model)
    swarm_cfg.validate_scale(b_model)
    return SCALE_A_ENDPOINT, a_model, SCALE_B_ENDPOINT, b_model

# Weighing prompt — single source of truth (per-dimension CoT, EXP-003 + APE EXP-004)
# NOTE: LLM prompt text uses "score" language because models were calibrated on it.
# Code uses "weight" language. DB columns use "judge_*"/"score" (legacy schema).
SCORING_PROMPT = """You are an expert data quality judge. Score the following AI training pair by evaluating each dimension independently. For instance, a score of 0.5 for specificity means the response is generic and not sufficiently tailored. Use these scoring anchors: 0.0-0.3 = poor, 0.4-0.6 = adequate, 0.7-0.8 = good, 0.9-1.0 = excellent.

SYSTEM PROMPT:
{system}

USER QUERY:
{user}

ASSISTANT RESPONSE:
{assistant}

Score EACH dimension from 0.00 to 1.00 with a brief justification, then compute the final score as the average.

Respond with ONLY a JSON object:
{{"accuracy": <float>, "accuracy_reason": "<1 sentence>", "completeness": <float>, "completeness_reason": "<1 sentence>", "specificity": <float>, "specificity_reason": "<1 sentence>", "structure": <float>, "structure_reason": "<1 sentence>", "domain_expertise": <float>, "domain_expertise_reason": "<1 sentence>", "score": <float average of 5 dimensions>, "reasoning": "<1 sentence summary>"}}"""

DRIFT_THRESHOLD = swarm_cfg.drift_threshold
DIMENSIONS = ("accuracy", "completeness", "specificity", "structure", "domain_expertise")

_running = True
def _shutdown(sig, frame):
    global _running
    log.info("Shutdown signal — finishing current batch...")
    _running = False
signal.signal(signal.SIGTERM, _shutdown)
signal.signal(signal.SIGINT, _shutdown)


def get_conn():
    import psycopg2
    if not DB_URL:
        log.error("DATABASE_URL not set")
        sys.exit(1)
    return psycopg2.connect(DB_URL, connect_timeout=10)


def classify(weight):
    """Weight class from swarm.yaml — single source of truth."""
    return swarm_cfg.classify(weight)


def weigh_pair(messages, endpoint, model):
    """Score a single pair via an ollama endpoint.
    Returns (score, reasoning, dims) or (None, error, None).
    dims is a dict: {accuracy: float, completeness: float, ...} or None on fallback.
    """
    sys_content = next((m["content"] for m in messages if m.get("role") == "system"), "")
    user_content = next((m["content"] for m in messages if m.get("role") == "user"), "")
    asst_content = next((m["content"] for m in messages if m.get("role") == "assistant"), "")

    prompt = SCORING_PROMPT.format(
        system=sys_content[:1000],
        user=user_content[:1500],
        assistant=asst_content[:2000],
    )

    payload = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1,
        "max_tokens": 512,
    }).encode()

    try:
        req = urllib.request.Request(
            f"{endpoint}/v1/chat/completions",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        resp = urllib.request.urlopen(req, timeout=180)
        data = json.loads(resp.read().decode())
        content = data["choices"][0]["message"]["content"]

        # Strip markdown fences
        content = re.sub(r"```json\s*", "", content)
        content = re.sub(r"```\s*", "", content)

        # Parse JSON — look for the full object with dimension keys
        json_match = re.search(r'\{[^{}]*"score"[^{}]*\}', content, re.DOTALL)
        if not json_match:
            # Try broader match for nested-looking responses
            json_match = re.search(r'\{.*"score"\s*:.*\}', content, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group())
            score = max(0.0, min(1.0, float(result["score"])))
            reasoning = result.get("reasoning", "")

            # Extract dimension scores
            dims = {}
            for d in DIMENSIONS:
                if d in result:
                    dims[d] = max(0.0, min(1.0, float(result[d])))
            # If we got all 5 dimensions, recompute score as their average
            if len(dims) == 5:
                score = round(sum(dims.values()) / 5, 4)

            return score, reasoning, dims if dims else None

        # Regex fallback — no dimensions available
        match = re.search(r'"score"\s*:\s*([\d.]+)', content)
        if match:
            return max(0.0, min(1.0, float(match.group(1)))), "parse_fallback", None

        return None, f"parse_error: {content[:100]}", None

    except Exception as e:
        return None, f"error: {str(e)[:100]}", None


def load_pairs(conn, domain, limit):
    """Load unscored pairs from the pairs table into the bin queue."""
    cur = conn.cursor()
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
    return loaded


def get_available_counts(conn):
    """Get count of unscored pairs per domain."""
    cur = conn.cursor()
    counts = {}
    for domain in DOMAIN_ORDER:
        cur.execute("""
            SELECT COUNT(*) FROM pairs p
            LEFT JOIN bin b ON b.pair_id = p.id
            WHERE p.domain_id = %s AND b.id IS NULL
        """, (domain,))
        counts[domain] = cur.fetchone()[0]
    return counts


def weigh_batch(conn):
    """Pull a batch from the bin, weigh through both scales with 2-pass validation."""
    cur = conn.cursor()

    # Lock a batch for scoring
    cur.execute("""
        UPDATE bin SET status = 'judging'
        WHERE id IN (
            SELECT id FROM bin WHERE status = 'queued' ORDER BY id LIMIT %s
            FOR UPDATE SKIP LOCKED
        )
        RETURNING id, pair_id
    """, (BATCH_SIZE,))
    batch = cur.fetchall()
    conn.commit()

    if not batch:
        return 0, 0, 0

    scored = 0
    flagged = 0
    errors = 0

    for bin_id, pair_id in batch:
        if not _running:
            # Requeue on shutdown
            cur.execute("UPDATE bin SET status = 'queued' WHERE id = %s", (bin_id,))
            conn.commit()
            break

        # Get messages + domain + prompt_hash from metadata
        cur.execute("SELECT messages, domain_id, metadata->>'prompt_hash' FROM pairs WHERE id = %s", (pair_id,))
        row = cur.fetchone()
        if not row or not row[0]:
            cur.execute("UPDATE bin SET status = 'queued' WHERE id = %s", (bin_id,))
            conn.commit()
            errors += 1
            continue

        messages = row[0] if isinstance(row[0], list) else json.loads(row[0])
        domain = row[1] or "unknown"
        prompt_hash = row[2]  # May be None if not in metadata

        # If no prompt_hash in metadata, compute from system prompt content
        if not prompt_hash:
            sys_content = next((m["content"] for m in messages if m.get("role") == "system"), "")
            if sys_content:
                prompt_hash = hashlib.sha256(sys_content.encode()).hexdigest()[:16]

        # ── Get scales for this domain ──
        scale_a_ep, scale_a_model, scale_b_ep, scale_b_model = get_scales(domain)

        # ── PASS 1: Both scales ──
        score_a1, reason_a, dims_a = weigh_pair(messages, scale_a_ep, scale_a_model)
        score_b1, reason_b, dims_b = weigh_pair(messages, scale_b_ep, scale_b_model)

        if score_a1 is None or score_b1 is None:
            log.warning("Bin %d: scale error A=%s B=%s — requeuing", bin_id, score_a1, score_b1)
            cur.execute("UPDATE bin SET status = 'queued' WHERE id = %s", (bin_id,))
            conn.commit()
            errors += 1
            continue

        # ── PASS 2: Validate the validator (dynamic — skip if strong agreement) ──
        # If both scales strongly agree (>0.90 and within 0.10 of each other),
        # skip Pass 2 to save 50% compute. The pair is clearly Royal Jelly.
        strong_agreement = (score_a1 >= 0.90 and score_b1 >= 0.90 and abs(score_a1 - score_b1) <= 0.10)

        if strong_agreement:
            score_a2 = score_a1  # Skip Pass 2 — use Pass 1 as both
            score_b2 = score_b1
        else:
            score_a2, _, _ = weigh_pair(messages, scale_a_ep, scale_a_model)
            score_b2, _, _ = weigh_pair(messages, scale_b_ep, scale_b_model)

            # Use pass 1 as fallback if pass 2 fails
            if score_a2 is None:
                score_a2 = score_a1
            if score_b2 is None:
                score_b2 = score_b1

        # Calculate drift
        drift_a = abs(score_a1 - score_a2)
        drift_b = abs(score_b1 - score_b2)
        max_drift = max(drift_a, drift_b)

        # Final scores (average of both passes)
        final_a = round((score_a1 + score_a2) / 2, 4)
        final_b = round((score_b1 + score_b2) / 2, 4)
        final_score = round((final_a + final_b) / 2, 4)
        tier = classify(final_score)

        # Generate deed ID
        deed_id = f"SB-{datetime.now(timezone.utc).strftime('%Y-%m%d')}-{bin_id:06d}"

        # Build dimension values for SQL (use Pass 1 dims, NULL if not available)
        dim_a_vals = tuple(dims_a.get(d) if dims_a else None for d in DIMENSIONS)
        dim_b_vals = tuple(dims_b.get(d) if dims_b else None for d in DIMENSIONS)

        status = 'flagged' if max_drift > DRIFT_THRESHOLD else 'scored'
        if status == 'flagged':
            flagged += 1
            log.debug("Bin %d: FLAGGED drift=%.3f (A:%.3f→%.3f B:%.3f→%.3f)",
                       bin_id, max_drift, score_a1, score_a2, score_b1, score_b2)
        else:
            scored += 1

        cur.execute("""
            UPDATE bin SET status = %s,
                judge_a_score = %s, judge_a_pass2 = %s, judge_a_reasoning = %s,
                judge_b_score = %s, judge_b_pass2 = %s, judge_b_reasoning = %s,
                judge_a_accuracy = %s, judge_a_completeness = %s, judge_a_specificity = %s,
                judge_a_structure = %s, judge_a_domain_expertise = %s,
                judge_b_accuracy = %s, judge_b_completeness = %s, judge_b_specificity = %s,
                judge_b_structure = %s, judge_b_domain_expertise = %s,
                final_score = %s, max_drift = %s, tier = %s,
                deed_id = %s, prompt_hash = %s, scored_at = NOW()
            WHERE id = %s
        """, (status,
              final_a, score_a2, reason_a[:500],
              final_b, score_b2, reason_b[:500],
              *dim_a_vals,
              *dim_b_vals,
              final_score, max_drift, tier,
              deed_id, prompt_hash, bin_id))

        conn.commit()

    return scored, flagged, errors


def run():
    log.info("═══ TRIBUNAL RUNNER STARTING ═══")
    log.info("  Batch:   %d pairs", BATCH_SIZE)
    log.info("  Cooldown: %ds", COOLDOWN)
    log.info("  Domains: %s", " → ".join(DOMAIN_ORDER))
    log.info("  Scale config (per domain):")
    seen = set()
    for domain in DOMAIN_ORDER:
        a_ep, a_model, b_ep, b_model = get_scales(domain)
        key = (a_ep, a_model, b_ep, b_model)
        if key not in seen:
            domains_with_key = [d for d in DOMAIN_ORDER if get_scales(d) == (a_ep, a_model, b_ep, b_model)]
            log.info("    %s: A=%s (%s) | B=%s (%s)", ",".join(domains_with_key), a_model, a_ep.split("//")[1], b_model, b_ep.split("//")[1])
            seen.add(key)
    # Also log heavy domains not in DOMAIN_ORDER
    for domain in DOMAIN_SCALES:
        if domain not in DOMAIN_ORDER:
            a_ep, a_model, b_ep, b_model = get_scales(domain)
            log.info("    %s (registered): A=%s | B=%s", domain, a_model, b_model)

    # Verify at least the default scales are reachable
    default_ep = DEFAULT_SCALE["a_endpoint"]
    default_model = DEFAULT_SCALE["a_model"]
    try:
        req = urllib.request.Request(f"{default_ep}/v1/chat/completions",
            data=json.dumps({"model": default_model, "messages": [{"role":"user","content":"ping"}], "max_tokens": 5}).encode(),
            headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=15)
        log.info("  Default scale endpoint: ONLINE")
    except Exception as e:
        log.warning("  Default scale endpoint: %s — %s (will retry per-domain)", default_ep, e)

    conn = None
    stats = {"total_weighed": 0, "total_flagged": 0, "total_errors": 0,
             "current_domain": None, "started": time.time()}
    domain_idx = 0

    while _running:
        try:
            # Reconnect if needed
            if conn is None or conn.closed:
                conn = get_conn()
                log.info("Connected to PostgreSQL")

            # Check available pairs
            available = get_available_counts(conn)
            total_available = sum(available.values())

            if total_available == 0:
                log.info("ALL DOMAINS EXHAUSTED — %d total weighed, %d flagged, %d errors",
                         stats["total_weighed"], stats["total_flagged"], stats["total_errors"])
                log.info("Sleeping 5 minutes before rechecking...")
                time.sleep(300)
                continue

            # Pick domain (smallest first, skip exhausted)
            domain = None
            for d in DOMAIN_ORDER:
                if available.get(d, 0) > 0:
                    domain = d
                    break

            if not domain:
                time.sleep(60)
                continue

            if domain != stats["current_domain"]:
                stats["current_domain"] = domain
                log.info("═══ DOMAIN: %s — %d pairs available ═══", domain.upper(), available[domain])

            # Load pairs into bin
            loaded = load_pairs(conn, domain, BATCH_SIZE)
            if loaded == 0:
                log.info("%s: no more pairs to load, moving to next domain", domain)
                # Remove this domain from front of order temporarily
                continue

            # Score the batch
            scored, flagged, errors = weigh_batch(conn)
            stats["total_weighed"] += scored
            stats["total_flagged"] += flagged
            stats["total_errors"] += errors

            elapsed = time.time() - stats["started"]
            rate = stats["total_weighed"] / max(elapsed / 3600, 0.001)

            log.info("%s: batch=%d weighed=%d flagged=%d errors=%d | total=%d (%.0f/hr) | remaining=%d",
                     domain, loaded, scored, flagged, errors,
                     stats["total_weighed"], rate, available[domain] - loaded)

            # Heartbeat every 100 scored
            if stats["total_weighed"] % 100 < BATCH_SIZE:
                log.info("HEARTBEAT: %d weighed, %d flagged, %d errors, %.0f/hr, uptime %.1fh",
                         stats["total_weighed"], stats["total_flagged"], stats["total_errors"],
                         rate, elapsed / 3600)
                for d in DOMAIN_ORDER:
                    log.info("  %s: %d remaining", d, available.get(d, 0))

        except Exception as e:
            log.error("Tribunal loop error: %s", e, exc_info=True)
            stats["total_errors"] += 1
            if conn:
                try:
                    conn.rollback()
                except Exception:
                    pass
                conn = None
            time.sleep(10)
            continue

        # Cooldown between batches
        time.sleep(COOLDOWN)

    # Shutdown
    if conn and not conn.closed:
        conn.close()

    elapsed = time.time() - stats["started"]
    log.info("═══ TRIBUNAL RUNNER STOPPED ═══")
    log.info("  Weighed: %d", stats["total_weighed"])
    log.info("  Flagged: %d", stats["total_flagged"])
    log.info("  Errors:  %d", stats["total_errors"])
    log.info("  Uptime:  %.1fh", elapsed / 3600)


if __name__ == "__main__":
    run()
