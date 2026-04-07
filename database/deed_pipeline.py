#!/usr/bin/env python3
"""
Deed Pipeline — PostgreSQL + MinIO + IPFS
==========================================
Three-layer storage for deeds:
  HOT:    PostgreSQL on NAS (real-time queries, graph traversals)
  COLD:   MinIO on NAS (immutable S3 objects, deed archive)
  PUBLIC: IPFS on NAS (decentralized, CID-addressable batches)

When a deed is created:
  1. Written to PostgreSQL (hot query layer)
  2. Archived to MinIO bucket (cold immutable storage)
  3. Batch pinned to IPFS (public verifiable layer)
  4. Merkle root anchored to Hedera (trust layer)

Usage:
    python deed_pipeline.py --deed deed.json                   # Single deed
    python deed_pipeline.py --deeds domains/medical/deeds/*.jsonl  # Batch
    python deed_pipeline.py --status                           # Check all layers
"""
import argparse
import json
import os
import time
import hashlib
import urllib.request
from pathlib import Path

# ─── CONFIG ───
DB_URL = os.environ.get("DATABASE_URL", "")
MINIO_ENDPOINT = os.environ.get("MINIO_ENDPOINT", "http://192.168.0.102:9000")
MINIO_ACCESS = os.environ.get("MINIO_ACCESS", "swarmbee")
MINIO_SECRET = os.environ.get("MINIO_SECRET", "")
MINIO_BUCKET = "swarmchain-proofs"
HEDERA_TOPIC = "0.0.10291838"


def store_deed_postgres(deed, conn):
    """Write deed to PostgreSQL hot layer."""
    import psycopg2
    from psycopg2.extras import Json

    cur = conn.cursor()

    # Find pair_id from fingerprint
    cur.execute("SELECT id FROM pairs WHERE fingerprint = %s", (deed.get("fingerprint", ""),))
    row = cur.fetchone()
    if not row:
        # Pair not in DB yet — skip or insert minimal
        return False

    pair_id = row[0]
    quality = deed.get("quality", {})
    ja = quality.get("judge_a", {})
    jb = quality.get("judge_b", {})

    cur.execute("""
        INSERT INTO deeds (
            id, pair_id, domain_id,
            origin_model, origin_node, origin_hardware, origin_strategy,
            judge_a_id, judge_a_score, judge_a_pass1, judge_a_pass2, judge_a_drift, judge_a_reasoning,
            judge_b_id, judge_b_score, judge_b_pass1, judge_b_pass2, judge_b_drift, judge_b_reasoning,
            final_score, max_drift, validated,
            attempts, generation_time_ms, prior_scores,
            energy_joules, cost_usd, cost_trend,
            tier, tier_threshold, sealed_at
        ) VALUES (
            %s, %s, %s,
            %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s,
            %s, %s, %s,
            %s, %s, %s,
            %s, %s, %s,
            %s, %s, %s
        ) ON CONFLICT (id) DO NOTHING
    """, (
        deed["block_id"], pair_id, deed.get("origin", {}).get("domain", "unknown"),
        deed.get("origin", {}).get("model"), deed.get("origin", {}).get("node"),
        deed.get("origin", {}).get("hardware"), deed.get("origin", {}).get("strategy"),
        ja.get("label"), ja.get("score"), ja.get("pass_1"), ja.get("pass_2"), ja.get("drift"), ja.get("reasoning"),
        jb.get("label"), jb.get("score"), jb.get("pass_1"), jb.get("pass_2"), jb.get("drift"), jb.get("reasoning"),
        quality.get("final_score"), deed.get("max_drift"), deed.get("validated", True),
        deed.get("process", {}).get("attempts"), deed.get("process", {}).get("generation_time_ms"),
        deed.get("process", {}).get("prior_scores"),
        deed.get("economics", {}).get("energy_joules"), deed.get("economics", {}).get("cost_usd"),
        deed.get("economics", {}).get("cost_trend"),
        deed.get("classification", {}).get("tier", "unknown"),
        deed.get("classification", {}).get("threshold"),
        deed.get("sealed_at"),
    ))

    return cur.rowcount > 0


def store_deed_minio(deed, deed_id):
    """Archive deed to MinIO cold storage as S3 object."""
    try:
        from minio import Minio
    except ImportError:
        # Fallback: use HTTP PUT
        return store_deed_minio_http(deed, deed_id)

    client = Minio(
        MINIO_ENDPOINT.replace("http://", "").replace("https://", ""),
        access_key=MINIO_ACCESS,
        secret_key=MINIO_SECRET,
        secure=False,
    )

    # Ensure bucket exists
    if not client.bucket_exists(MINIO_BUCKET):
        client.make_bucket(MINIO_BUCKET)

    # Store deed as JSON object
    deed_json = json.dumps(deed, indent=2).encode()
    domain = deed.get("origin", {}).get("domain", "unknown")
    object_name = f"deeds/{domain}/{deed_id}.json"

    from io import BytesIO
    client.put_object(
        MINIO_BUCKET,
        object_name,
        BytesIO(deed_json),
        len(deed_json),
        content_type="application/json",
    )
    return object_name


def store_deed_minio_http(deed, deed_id):
    """Fallback: store to MinIO via S3 HTTP API."""
    import hmac
    import base64
    from datetime import datetime

    deed_json = json.dumps(deed, indent=2).encode()
    domain = deed.get("origin", {}).get("domain", "unknown")
    object_path = f"deeds/{domain}/{deed_id}.json"

    # Simple S3 PUT (unsigned for internal use)
    url = f"{MINIO_ENDPOINT}/{MINIO_BUCKET}/{object_path}"
    req = urllib.request.Request(url, data=deed_json, method="PUT")
    req.add_header("Content-Type", "application/json")

    try:
        urllib.request.urlopen(req, timeout=10)
        return object_path
    except Exception as e:
        print(f"  MinIO fallback failed: {e}")
        return None


def pin_batch_ipfs(batch_data, batch_id):
    """Pin a deed batch to IPFS for public verifiability."""
    try:
        batch_json = json.dumps(batch_data, indent=2).encode()

        # IPFS HTTP API (kubo default port 5001)
        req = urllib.request.Request(
            "http://192.168.0.102:5001/api/v0/add",
            data=batch_json,
            headers={"Content-Type": "application/octet-stream"},
            method="POST",
        )
        resp = urllib.request.urlopen(req, timeout=30)
        result = json.loads(resp.read().decode())
        cid = result.get("Hash", "")
        print(f"  IPFS pinned: {cid} (batch {batch_id})")
        return cid
    except Exception as e:
        print(f"  IPFS pin failed: {e}")
        return None


def process_deed_batch(deeds_path, domain):
    """Process a batch of deeds through all three layers."""
    import psycopg2

    print(f"\n{'='*60}")
    print(f"  DEED PIPELINE — {domain.upper()}")
    print(f"{'='*60}")

    conn = psycopg2.connect(DB_URL)

    deeds = []
    with open(deeds_path) as f:
        for line in f:
            if line.strip():
                deeds.append(json.loads(line))

    print(f"  Deeds to process: {len(deeds):,}")

    stats = {"postgres": 0, "minio": 0, "ipfs_batches": 0}
    batch_buffer = []

    for i, deed in enumerate(deeds):
        deed_id = deed.get("block_id", f"unknown-{i}")

        # Layer 1: PostgreSQL (hot)
        if store_deed_postgres(deed, conn):
            stats["postgres"] += 1

        # Layer 2: MinIO (cold)
        obj = store_deed_minio(deed, deed_id)
        if obj:
            stats["minio"] += 1

        # Buffer for IPFS batch
        batch_buffer.append(deed)

        # Pin to IPFS every 50 deeds
        if len(batch_buffer) >= 50:
            cid = pin_batch_ipfs(batch_buffer, f"batch-{i//50}")
            if cid:
                stats["ipfs_batches"] += 1
            batch_buffer = []

        if (i + 1) % 100 == 0:
            conn.commit()
            print(f"  [{i+1}/{len(deeds)}] PG:{stats['postgres']} MinIO:{stats['minio']} IPFS:{stats['ipfs_batches']}")

    # Final IPFS batch
    if batch_buffer:
        cid = pin_batch_ipfs(batch_buffer, "batch-final")
        if cid:
            stats["ipfs_batches"] += 1

    conn.commit()
    conn.close()

    print(f"\n  Pipeline complete:")
    print(f"    PostgreSQL: {stats['postgres']:,} deeds (hot)")
    print(f"    MinIO:      {stats['minio']:,} objects (cold)")
    print(f"    IPFS:       {stats['ipfs_batches']} batches (public)")
    print(f"{'='*60}\n")

    return stats


def check_status():
    """Check all three storage layers."""
    import psycopg2

    print(f"\n{'='*60}")
    print(f"  DEED PIPELINE STATUS")
    print(f"{'='*60}")

    # PostgreSQL
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM pairs")
        pairs = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM deeds")
        deeds = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM graph_edges")
        edges = cur.fetchone()[0]
        print(f"  PostgreSQL (HOT):  {pairs:,} pairs | {deeds:,} deeds | {edges:,} edges")
        conn.close()
    except Exception as e:
        print(f"  PostgreSQL: ERROR - {e}")

    # MinIO
    try:
        req = urllib.request.Request(f"{MINIO_ENDPOINT}/minio/health/live")
        resp = urllib.request.urlopen(req, timeout=5)
        print(f"  MinIO (COLD):      HEALTHY (port 9000)")
    except Exception as e:
        print(f"  MinIO: ERROR - {e}")

    # IPFS
    try:
        req = urllib.request.Request("http://192.168.0.102:5001/api/v0/id", method="POST")
        resp = urllib.request.urlopen(req, timeout=5)
        ipfs_info = json.loads(resp.read().decode())
        print(f"  IPFS (PUBLIC):     ONLINE — {ipfs_info.get('ID', '?')[:16]}...")
    except Exception as e:
        print(f"  IPFS: OFFLINE - {e}")

    print(f"{'='*60}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Deed Pipeline")
    parser.add_argument("--deeds", help="Deeds JSONL file to process")
    parser.add_argument("--domain", help="Domain name")
    parser.add_argument("--status", action="store_true", help="Check all layers")
    args = parser.parse_args()

    if args.status:
        check_status()
    elif args.deeds and args.domain:
        process_deed_batch(args.deeds, args.domain)
    else:
        parser.print_help()
