#!/usr/bin/env python3
"""
Domain Preparation — Glass Wall Pipeline
==========================================
Converts all domain datasets into tribunal-ready format.
Every domain follows the same path:

    raw/ → tribunal_ready/ → scored/ → deeds/ → royal_jelly/

Medical pairs get converted from question/answer → system/user/assistant.
CRE and aviation pairs get standardized from cell format → messages format.
Grants pairs are already deeded — pass through for re-tribunal with Gemma 4.

Usage:
    python prepare_domains.py --domain medical
    python prepare_domains.py --domain cre
    python prepare_domains.py --domain aviation
    python prepare_domains.py --domain grants
    python prepare_domains.py --domain all
"""
import argparse
import json
import hashlib
from pathlib import Path
from collections import Counter

REPO = Path(__file__).parent.parent
DOMAINS_DIR = REPO / "domains"

# ─── MEDICAL SYSTEM PROMPTS BY SPECIALTY ───
MEDICAL_SYSTEM_PROMPTS = {
    "default": (
        "You are a board-certified physician providing evidence-based clinical guidance. "
        "Your responses should be thorough, cite relevant medical literature where applicable, "
        "and consider differential diagnoses. Always note when imaging, labs, or specialist "
        "referral would be appropriate."
    ),
    "neuroradiology": (
        "You are a board-certified neuroradiologist. Interpret imaging findings systematically "
        "by anatomical level. Report disc morphology, signal characteristics, neural compromise, "
        "and clinical correlation. Use structured reporting format."
    ),
    "surgery": (
        "You are a board-certified surgeon. Evaluate surgical indications, operative approach, "
        "risk stratification, and post-operative management. Consider minimally invasive options "
        "where appropriate and discuss expected outcomes."
    ),
    "pharmacology": (
        "You are a clinical pharmacologist. Evaluate drug mechanisms, interactions, dosing "
        "considerations, contraindications, and therapeutic monitoring. Consider patient-specific "
        "factors including renal/hepatic function, age, and comorbidities."
    ),
    "cardiology": (
        "You are a board-certified cardiologist. Interpret cardiac findings, evaluate risk factors, "
        "recommend diagnostic workup, and discuss evidence-based treatment options. Consider ACC/AHA "
        "guidelines where applicable."
    ),
    "pediatrics": (
        "You are a board-certified pediatrician. Consider age-appropriate differential diagnoses, "
        "growth and developmental milestones, vaccination status, and family history. Adjust dosing "
        "and management for pediatric populations."
    ),
    "psychiatry": (
        "You are a board-certified psychiatrist. Evaluate psychiatric presentations using DSM-5 "
        "criteria, consider comorbid conditions, and recommend evidence-based pharmacological and "
        "therapeutic interventions. Assess safety risk factors."
    ),
}


def fingerprint(messages):
    """SHA256 fingerprint for deduplication."""
    content = json.dumps(messages, sort_keys=True, ensure_ascii=True)
    return hashlib.sha256(content.encode()).hexdigest()


def convert_medical(input_paths, output_path, max_pairs=None):
    """Convert medical question/answer pairs to tribunal-ready messages format."""

    print(f"[medical] Converting to tribunal format...")
    all_pairs = []

    for path in input_paths:
        if not Path(path).exists():
            print(f"  SKIP: {path}")
            continue
        count = 0
        with open(path) as f:
            for line in f:
                if line.strip():
                    try:
                        pair = json.loads(line)
                        all_pairs.append(pair)
                        count += 1
                    except json.JSONDecodeError:
                        pass
        print(f"  Loaded {count:,} from {path}")

    print(f"  Total raw: {len(all_pairs):,}")

    # Convert to messages format
    converted = []
    seen = set()
    specialty_counts = Counter()

    for pair in all_pairs:
        question = pair.get("question", "").strip()
        answer = pair.get("answer", "").strip()
        specialty = pair.get("specialty", "general")
        tier = pair.get("tier", "unknown")

        if not question or not answer:
            continue

        # Get specialty-specific system prompt
        system_prompt = MEDICAL_SYSTEM_PROMPTS.get(
            specialty, MEDICAL_SYSTEM_PROMPTS["default"]
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": question},
            {"role": "assistant", "content": answer},
        ]

        # Deduplicate
        fp = fingerprint(messages)
        if fp in seen:
            continue
        seen.add(fp)

        converted.append({
            "messages": messages,
            "metadata": {
                "domain": "medical",
                "specialty": specialty,
                "source_tier": tier,
                "source_id": pair.get("id", ""),
                "fingerprint": fp,
            },
        })
        specialty_counts[specialty] += 1

    if max_pairs and len(converted) > max_pairs:
        converted = converted[:max_pairs]

    # Write
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        for c in converted:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")

    print(f"  Converted: {len(converted):,}")
    print(f"  Specialties: {len(specialty_counts)}")
    print(f"  Top 5:")
    for s, c in specialty_counts.most_common(5):
        print(f"    {s}: {c:,}")
    print(f"  Output: {output_path}")
    return len(converted)


def convert_cre(input_paths, output_path, max_pairs=None):
    """Standardize CRE pairs — already in messages format, just normalize metadata."""

    print(f"[cre] Standardizing for tribunal...")
    converted = []
    seen = set()

    for path in input_paths:
        if not Path(path).exists():
            print(f"  SKIP: {path}")
            continue
        count = 0
        with open(path) as f:
            for line in f:
                if line.strip():
                    try:
                        pair = json.loads(line)
                        messages = pair.get("messages", [])
                        if not messages or len(messages) < 2:
                            continue

                        fp = fingerprint(messages)
                        if fp in seen:
                            continue
                        seen.add(fp)

                        converted.append({
                            "messages": messages,
                            "metadata": {
                                "domain": "cre",
                                "cluster": pair.get("cluster", ""),
                                "source_grade": pair.get("grade", ""),
                                "source_score": pair.get("verification_score", None),
                                "fingerprint": fp,
                            },
                        })
                        count += 1
                    except json.JSONDecodeError:
                        pass
        print(f"  Loaded {count:,} from {path}")

    if max_pairs and len(converted) > max_pairs:
        converted = converted[:max_pairs]

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        for c in converted:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")

    print(f"  Tribunal-ready: {len(converted):,}")
    print(f"  Output: {output_path}")
    return len(converted)


def convert_aviation(input_paths, output_path, max_pairs=None):
    """Standardize aviation pairs — already in messages format with lineage."""

    print(f"[aviation] Standardizing for tribunal...")
    converted = []
    seen = set()

    for path in sorted(input_paths):
        if not Path(path).exists():
            continue
        count = 0
        with open(path) as f:
            for line in f:
                if line.strip():
                    try:
                        pair = json.loads(line)
                        messages = pair.get("messages", [])
                        if not messages or len(messages) < 2:
                            continue

                        fp = fingerprint(messages)
                        if fp in seen:
                            continue
                        seen.add(fp)

                        converted.append({
                            "messages": messages,
                            "metadata": {
                                "domain": "aviation",
                                "source_grade": pair.get("grade", ""),
                                "source_score": pair.get("verification_score", None),
                                "lineage": pair.get("lineage", {}),
                                "task_type": pair.get("task_type", ""),
                                "fingerprint": fp,
                            },
                        })
                        count += 1
                    except json.JSONDecodeError:
                        pass
        print(f"  Loaded {count:,} from {Path(path).name}")

    if max_pairs and len(converted) > max_pairs:
        converted = converted[:max_pairs]

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        for c in converted:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")

    print(f"  Tribunal-ready: {len(converted):,}")
    print(f"  Output: {output_path}")
    return len(converted)


def convert_grants(input_paths, output_path, max_pairs=None):
    """Grants already have deeds — standardize metadata for re-tribunal with Gemma 4."""

    print(f"[grants] Preparing for Gemma 4 re-tribunal...")
    converted = []
    seen = set()
    deeded = 0

    for path in input_paths:
        if not Path(path).exists():
            print(f"  SKIP: {path}")
            continue
        count = 0
        with open(path) as f:
            for line in f:
                if line.strip():
                    try:
                        pair = json.loads(line)
                        messages = pair.get("messages", [])
                        if not messages or len(messages) < 2:
                            continue

                        fp = fingerprint(messages)
                        if fp in seen:
                            continue
                        seen.add(fp)

                        has_deed = "swarmchain_deed" in pair
                        if has_deed:
                            deeded += 1

                        converted.append({
                            "messages": messages,
                            "metadata": {
                                "domain": "grants",
                                "source_tier": pair.get("metadata", {}).get("tier", ""),
                                "source_score": pair.get("metadata", {}).get("score", None),
                                "has_prior_deed": has_deed,
                                "prior_deed": pair.get("swarmchain_deed", None),
                                "fingerprint": fp,
                            },
                        })
                        count += 1
                    except json.JSONDecodeError:
                        pass
        print(f"  Loaded {count:,} from {path} ({deeded:,} with prior deeds)")

    if max_pairs and len(converted) > max_pairs:
        converted = converted[:max_pairs]

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        for c in converted:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")

    print(f"  Tribunal-ready: {len(converted):,} ({deeded:,} with prior deeds)")
    print(f"  Output: {output_path}")
    return len(converted)


# ─── SOURCE MAPPING ───
import glob

DOMAIN_CONFIG = {
    "medical": {
        "sources": [
            "/data1/swarm-honey/medical/MASTER_PLATINUM.jsonl",
            "/data1/swarm-honey/medical/MASTER_GOLD.jsonl",
        ],
        "converter": convert_medical,
    },
    "cre": {
        "sources": [
            "/data1/swarm-honey/cre/cre_honey_stamped.jsonl",
        ],
        "converter": convert_cre,
    },
    "aviation": {
        "sources": sorted(glob.glob("/data2/hive_audit/finalized/aviation_*.jsonl")),
        "converter": convert_aviation,
    },
    "grants": {
        "sources": [
            "/home/swarm/swarmwriter-nemotron70b/swarmwriter_full.jsonl",
        ],
        "converter": convert_grants,
    },
}


def prepare_domain(domain, max_pairs=None):
    """Prepare a single domain for tribunal."""
    config = DOMAIN_CONFIG.get(domain)
    if not config:
        print(f"Unknown domain: {domain}")
        return 0

    output = DOMAINS_DIR / domain / "tribunal_ready" / f"{domain}_tribunal_ready.jsonl"
    return config["converter"](config["sources"], str(output), max_pairs)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Domain Preparation — Glass Wall")
    parser.add_argument("--domain", required=True, help="Domain: medical, cre, aviation, grants, all")
    parser.add_argument("--max-pairs", type=int, help="Cap pairs per domain")
    args = parser.parse_args()

    print("=" * 60)
    print("  SWARM & BEE — GLASS WALL DOMAIN PREPARATION")
    print("=" * 60)
    print()

    if args.domain == "all":
        total = 0
        for domain in DOMAIN_CONFIG:
            count = prepare_domain(domain, args.max_pairs)
            total += count
            print()
        print(f"{'='*60}")
        print(f"  TOTAL: {total:,} pairs across {len(DOMAIN_CONFIG)} domains")
        print(f"{'='*60}")
    else:
        prepare_domain(args.domain, args.max_pairs)
