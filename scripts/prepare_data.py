#!/usr/bin/env python3
"""
Data Preparation Pipeline
=========================
Consolidates all domain datasets for tribunal processing.
Validates format, deduplicates, and produces clean JSONL ready for scoring.

Data locations (Swarmrails):
    Medical PLATINUM: /data1/swarm-honey/medical/MASTER_PLATINUM.jsonl  (406K)
    Medical GOLD:     /data1/swarm-honey/medical/MASTER_GOLD.jsonl     (386K)
    CRE Stamped:      /data1/swarm-honey/cre/cre_honey_stamped.jsonl   (810K)
    Aviation:         /data2/hive_audit/finalized/aviation_*.jsonl      (42K)
    Grants:           /home/swarm/swarmwriter-nemotron70b/swarmwriter_full.jsonl (36K)

Usage:
    python prepare_data.py --domain medical --output tribunal_input/medical.jsonl
    python prepare_data.py --domain aviation --output tribunal_input/aviation.jsonl
    python prepare_data.py --domain cre --output tribunal_input/cre.jsonl
    python prepare_data.py --domain grants --output tribunal_input/grants.jsonl
    python prepare_data.py --domain all --output-dir tribunal_input/
"""
import argparse
import json
import hashlib
import glob
from pathlib import Path

SOURCES = {
    "medical": [
        "/data1/swarm-honey/medical/MASTER_PLATINUM.jsonl",
        "/data1/swarm-honey/medical/MASTER_GOLD.jsonl",
    ],
    "cre": [
        "/data1/swarm-honey/cre/cre_honey_stamped.jsonl",
    ],
    "aviation": sorted(glob.glob("/data2/hive_audit/finalized/aviation_*.jsonl")),
    "grants": [
        "/home/swarm/swarmwriter-nemotron70b/swarmwriter_full.jsonl",
    ],
}


def validate_pair(pair):
    """Validate a training pair has required structure."""
    messages = pair.get("messages", [])
    if not messages or len(messages) < 2:
        return False

    roles = [m.get("role") for m in messages]
    if "user" not in roles or "assistant" not in roles:
        return False

    # Check for minimum content
    for m in messages:
        if not m.get("content", "").strip():
            return False

    return True


def fingerprint(messages):
    """SHA256 fingerprint for deduplication."""
    content = json.dumps(messages, sort_keys=True, ensure_ascii=True)
    return hashlib.sha256(content.encode()).hexdigest()


def prepare_domain(domain, output_path, max_pairs=None):
    """Load, validate, deduplicate, and export a domain's data."""

    sources = SOURCES.get(domain, [])
    if not sources:
        print(f"[prep] Unknown domain: {domain}")
        return 0

    print(f"[prep] Domain: {domain}")
    print(f"[prep] Sources: {len(sources)} files")

    all_pairs = []
    for src in sources:
        if not Path(src).exists():
            print(f"  SKIP (not found): {src}")
            continue

        count = 0
        with open(src) as f:
            for line in f:
                if line.strip():
                    try:
                        pair = json.loads(line)
                        all_pairs.append(pair)
                        count += 1
                    except json.JSONDecodeError:
                        pass
        print(f"  Loaded {count:,} from {src}")

    print(f"[prep] Total raw: {len(all_pairs):,}")

    # Validate
    valid = [p for p in all_pairs if validate_pair(p)]
    print(f"[prep] Valid: {len(valid):,} ({len(valid)/max(len(all_pairs),1)*100:.1f}%)")

    # Deduplicate by message content fingerprint
    seen = set()
    deduped = []
    for p in valid:
        fp = fingerprint(p["messages"])
        if fp not in seen:
            seen.add(fp)
            deduped.append(p)
    print(f"[prep] Deduped: {len(deduped):,} (removed {len(valid)-len(deduped):,} duplicates)")

    # Cap if requested
    if max_pairs and len(deduped) > max_pairs:
        deduped = deduped[:max_pairs]
        print(f"[prep] Capped at {max_pairs:,}")

    # Write output
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        for p in deduped:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")

    print(f"[prep] Output: {output_path} ({len(deduped):,} pairs)")
    return len(deduped)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Data Preparation")
    parser.add_argument("--domain", required=True, help="Domain: medical, cre, aviation, grants, all")
    parser.add_argument("--output", help="Output JSONL path (for single domain)")
    parser.add_argument("--output-dir", default="tribunal_input", help="Output directory (for --domain all)")
    parser.add_argument("--max-pairs", type=int, help="Cap pairs per domain")
    args = parser.parse_args()

    if args.domain == "all":
        total = 0
        for domain in SOURCES:
            out = f"{args.output_dir}/{domain}.jsonl"
            total += prepare_domain(domain, out, args.max_pairs)
            print()
        print(f"[prep] All domains: {total:,} total pairs")
    else:
        output = args.output or f"tribunal_input/{args.domain}.jsonl"
        prepare_domain(args.domain, output, args.max_pairs)
