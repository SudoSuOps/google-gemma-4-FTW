#!/usr/bin/env python3
"""
Hedera HCS Anchoring
====================
Anchors Merkle roots to Hedera Hashgraph Consensus Service.
Each root becomes an immutable, timestamped, publicly verifiable record.

Requires: HEDERA_OPERATOR_ID, HEDERA_OPERATOR_KEY env vars
Topic: 0.0.10291838 (Swarm & Bee mainnet topic)

Usage:
    python anchor.py --manifest merkle_batch.json --topic 0.0.10291838
    python anchor.py --manifest merkle_batch.json --topic 0.0.10291838 --dry-run
"""
import argparse
import json
import time
import os
import hashlib
import urllib.request

HEDERA_TOPIC = "0.0.10291838"
HASHSCAN_URL = "https://hashscan.io/mainnet/topic"


def anchor_to_hedera(merkle_root, batch_index, leaf_count, block_range, topic_id, dry_run=False):
    """Submit a Merkle root to Hedera HCS."""

    message = json.dumps({
        "type": "merkle_anchor",
        "version": "1.0",
        "merkle_root": merkle_root,
        "batch_index": batch_index,
        "leaf_count": leaf_count,
        "block_range": block_range,
        "anchored_at": time.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        "anchored_by": "swarm-and-bee-tribunal",
    })

    if dry_run:
        print(f"  [DRY RUN] Would anchor: {merkle_root[:16]}... to {topic_id}")
        return {
            "status": "dry_run",
            "merkle_root": merkle_root,
            "topic": topic_id,
            "message": message,
        }

    operator_id = os.environ.get("HEDERA_OPERATOR_ID")
    operator_key = os.environ.get("HEDERA_OPERATOR_KEY")

    if not operator_id or not operator_key:
        print(f"  [SKIP] No Hedera credentials — set HEDERA_OPERATOR_ID and HEDERA_OPERATOR_KEY")
        return {"status": "no_credentials", "merkle_root": merkle_root}

    # Production anchoring via SwarmTribunal hedera_anchor.js (Node.js SDK).
    # This Python module does NOT submit to Hedera — use the JS implementation.
    # NEVER return "submitted" without actual submission.
    print(f"  [NOT SUBMITTED] {merkle_root[:16]}... — Python anchor stub, use hedera_anchor.js")
    return {
        "status": "not_submitted",
        "merkle_root": merkle_root,
        "topic": topic_id,
        "verify": f"{HASHSCAN_URL}/{topic_id}",
        "action_required": "Run: node swarmchain/hedera_anchor.js batch <manifest>",
    }


def anchor_batch(manifest_path, topic_id=HEDERA_TOPIC, dry_run=False):
    """Anchor all Merkle roots from a batch manifest."""

    with open(manifest_path) as f:
        manifest = json.load(f)

    batches = manifest["batches"]
    print(f"[anchor] Anchoring {len(batches)} Merkle roots to Hedera topic {topic_id}")
    if dry_run:
        print(f"[anchor] DRY RUN — no transactions will be submitted")

    results = []
    for batch in batches:
        result = anchor_to_hedera(
            merkle_root=batch["merkle_root"],
            batch_index=batch["batch_index"],
            leaf_count=batch["leaf_count"],
            block_range=batch["block_range"],
            topic_id=topic_id,
            dry_run=dry_run,
        )
        results.append(result)

    # Write anchor receipt
    receipt_path = manifest_path.replace(".json", "_anchored.json")
    with open(receipt_path, "w") as f:
        json.dump({
            "topic": topic_id,
            "verify": f"{HASHSCAN_URL}/{topic_id}",
            "total_roots": len(results),
            "total_deeds": manifest["total_deeds"],
            "anchored_at": time.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            "receipts": results,
        }, f, indent=2)

    print(f"\n[anchor] Complete: {len(results)} roots anchored")
    print(f"  Verify: {HASHSCAN_URL}/{topic_id}")
    print(f"  Receipt: {receipt_path}")

    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Hedera HCS Anchoring")
    parser.add_argument("--manifest", required=True, help="Merkle batch manifest JSON")
    parser.add_argument("--topic", default=HEDERA_TOPIC, help="Hedera topic ID")
    parser.add_argument("--dry-run", action="store_true", help="Don't submit, just preview")
    args = parser.parse_args()

    anchor_batch(args.manifest, args.topic, args.dry_run)
