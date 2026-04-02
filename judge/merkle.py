#!/usr/bin/env python3
"""
Merkle Tree Builder
===================
Builds SHA256 Merkle trees from batches of deeds.
The root is what gets anchored to Hedera HCS.

Usage:
    python merkle.py --input deeds.jsonl --output merkle_batch.json
"""
import argparse
import json
import hashlib
from pathlib import Path


def sha256(data):
    """SHA256 hash of a string."""
    return hashlib.sha256(data.encode()).hexdigest()


def build_merkle_tree(leaves):
    """Build a Merkle tree from a list of leaf hashes. Returns (root, tree)."""
    if not leaves:
        return None, []

    tree = [leaves[:]]

    current_level = leaves[:]
    while len(current_level) > 1:
        next_level = []
        for i in range(0, len(current_level), 2):
            left = current_level[i]
            right = current_level[i + 1] if i + 1 < len(current_level) else left
            parent = sha256(left + right)
            next_level.append(parent)
        tree.append(next_level)
        current_level = next_level

    root = current_level[0] if current_level else None
    return root, tree


def get_merkle_proof(tree, leaf_index):
    """Get the Merkle proof (sibling hashes) for a leaf at the given index."""
    proof = []
    idx = leaf_index

    for level in tree[:-1]:
        if idx % 2 == 0:
            sibling_idx = idx + 1
            direction = "right"
        else:
            sibling_idx = idx - 1
            direction = "left"

        if sibling_idx < len(level):
            proof.append({"hash": level[sibling_idx], "direction": direction})
        else:
            proof.append({"hash": level[idx], "direction": direction})

        idx = idx // 2

    return proof


def verify_merkle_proof(leaf_hash, proof, expected_root):
    """Verify a Merkle proof against an expected root."""
    current = leaf_hash
    for step in proof:
        if step["direction"] == "right":
            current = sha256(current + step["hash"])
        else:
            current = sha256(step["hash"] + current)
    return current == expected_root


def build_from_deeds(input_path, output_path, batch_size=50):
    """Build Merkle trees from deed files in batches."""

    deeds = []
    with open(input_path) as f:
        for line in f:
            if line.strip():
                deeds.append(json.loads(line))

    print(f"[merkle] Processing {len(deeds):,} deeds in batches of {batch_size}")

    batches = []
    for batch_start in range(0, len(deeds), batch_size):
        batch = deeds[batch_start:batch_start + batch_size]

        # Create leaf hashes from deed fingerprints + scores
        leaves = []
        for deed in batch:
            leaf_data = json.dumps({
                "block_id": deed["block_id"],
                "fingerprint": deed["fingerprint"],
                "score": deed["quality"]["final_score"],
                "tier": deed["classification"]["tier"],
                "sealed_at": deed["sealed_at"],
            }, sort_keys=True)
            leaves.append(sha256(leaf_data))

        root, tree = build_merkle_tree(leaves)

        # Update deeds with Merkle info
        for i, deed in enumerate(batch):
            deed["trust"]["merkle_root"] = root
            deed["trust"]["merkle_leaf_index"] = i

        batch_info = {
            "batch_index": batch_start // batch_size,
            "merkle_root": root,
            "leaf_count": len(leaves),
            "block_range": f"{batch[0]['block_id']} — {batch[-1]['block_id']}",
            "leaves": leaves,
        }
        batches.append(batch_info)
        print(f"  Batch {batch_info['batch_index']}: {root[:16]}... ({len(leaves)} leaves)")

    # Write updated deeds back
    with open(input_path, "w") as f:
        for d in deeds:
            f.write(json.dumps(d, ensure_ascii=False) + "\n")

    # Write batch manifest
    with open(output_path, "w") as f:
        json.dump({
            "total_deeds": len(deeds),
            "total_batches": len(batches),
            "batch_size": batch_size,
            "batches": batches,
        }, f, indent=2)

    print(f"\n[merkle] {len(batches)} Merkle roots ready for Hedera anchoring")
    print(f"  Deeds updated: {input_path}")
    print(f"  Batch manifest: {output_path}")

    return batches


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Merkle Tree Builder")
    parser.add_argument("--input", required=True, help="Deeds JSONL file")
    parser.add_argument("--output", required=True, help="Output batch manifest JSON")
    parser.add_argument("--batch-size", type=int, default=50, help="Deeds per Merkle batch")
    args = parser.parse_args()

    build_from_deeds(args.input, args.output, args.batch_size)
