#!/usr/bin/env python3
"""
Title Deed Generator
====================
Converts tribunal-scored pairs into formal title deeds.
Every deed carries five proofs: origin, quality, process, economics, trust.

Usage:
    python deed.py --input scored.jsonl --output deeds.jsonl --domain healthcare
"""
import argparse
import json
import time
import hashlib
from pathlib import Path


def generate_deed(scored_pair, domain, hardware="unknown", node="unknown", strategy="tribunal_dual_judge"):
    """Generate a formal title deed from a tribunal-scored pair."""

    tribunal = scored_pair.get("tribunal", {})
    if not tribunal:
        return None

    block_id = tribunal["block_id"]
    messages = scored_pair.get("messages", [])

    deed = {
        "block_id": block_id,
        "version": "1.0",

        # Proof 01: Origin
        "origin": {
            "domain": domain,
            "model": scored_pair.get("lineage", {}).get("model", "unknown"),
            "node": node,
            "hardware": hardware,
            "strategy": strategy,
        },

        # Proof 02: Quality
        "quality": {
            "judge_a": tribunal["judge_a"],
            "judge_b": tribunal["judge_b"],
            "final_score": tribunal["final_score"],
        },

        # Proof 03: Process
        "process": {
            "attempts": scored_pair.get("lineage", {}).get("attempts", 1),
            "generation_time_ms": tribunal["generation_time_ms"],
            "prior_scores": scored_pair.get("lineage", {}).get("prior_scores", []),
        },

        # Proof 04: Economics (populated during batch close)
        "economics": {
            "energy_joules": None,
            "cost_usd": None,
            "cost_trend": None,
        },

        # Proof 05: Trust (populated during anchoring)
        "trust": {
            "merkle_root": None,
            "merkle_leaf_index": None,
            "hedera_topic": None,
            "hedera_sequence": None,
            "hedera_timestamp": None,
        },

        # Classification
        "classification": tribunal["classification"],

        # Seal
        "sealed_at": tribunal["sealed_at"],
        "fingerprint": tribunal["fingerprint"],
    }

    return deed


def generate_deeds(input_path, output_path, domain, hardware="unknown", node="unknown"):
    """Process all scored pairs into deeds."""

    scored = []
    with open(input_path) as f:
        for line in f:
            if line.strip():
                scored.append(json.loads(line))

    print(f"[deed] Generating deeds for {len(scored):,} scored pairs")
    print(f"[deed] Domain: {domain}")

    deeds = []
    stats = {"royal_jelly": 0, "honey": 0, "propolis": 0}

    for pair in scored:
        deed = generate_deed(pair, domain, hardware, node)
        if deed:
            deeds.append(deed)
            tier = deed["classification"]["tier"]
            stats[tier] += 1

    # Write deeds
    with open(output_path, "w") as f:
        for d in deeds:
            f.write(json.dumps(d, ensure_ascii=False) + "\n")

    print(f"[deed] Generated {len(deeds):,} deeds")
    print(f"  Royal Jelly: {stats['royal_jelly']:,}")
    print(f"  Honey:       {stats['honey']:,}")
    print(f"  Propolis:    {stats['propolis']:,}")
    print(f"  Output:      {output_path}")

    return deeds


def extract_royal_jelly(deeds_path, output_path):
    """Extract only Royal Jelly pairs for writer training."""

    rj_count = 0
    total = 0
    with open(deeds_path) as fin, open(output_path, "w") as fout:
        for line in fin:
            if not line.strip():
                continue
            deed = json.loads(line)
            total += 1
            if deed["classification"]["tier"] == "royal_jelly":
                fout.write(line)
                rj_count += 1

    print(f"[deed] Extracted {rj_count:,} Royal Jelly from {total:,} total ({rj_count/max(total,1)*100:.1f}%)")
    print(f"  Output: {output_path}")
    return rj_count


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Title Deed Generator")
    parser.add_argument("--input", required=True, help="Tribunal-scored JSONL")
    parser.add_argument("--output", required=True, help="Output deeds JSONL")
    parser.add_argument("--domain", required=True, help="Domain (healthcare, aviation, grants, cre)")
    parser.add_argument("--hardware", default="unknown", help="Hardware identifier")
    parser.add_argument("--node", default="unknown", help="Node identifier")
    parser.add_argument("--extract-rj", help="Also extract Royal Jelly pairs to this file")
    args = parser.parse_args()

    deeds = generate_deeds(args.input, args.output, args.domain, args.hardware, args.node)

    if args.extract_rj:
        extract_royal_jelly(args.output, args.extract_rj)
