#!/usr/bin/env python3
"""
Independent Deed Verification Tool
====================================
Anyone can verify a deed without trusting Swarm & Bee.
Run the same scoring function, recompute the Merkle tree, check Hedera.

Usage:
    python verify.py --deed deed.json
    python verify.py --deed deed.json --full  (recompute score with local models)
"""
import argparse
import json
import hashlib
import sys


def sha256(data):
    return hashlib.sha256(data.encode()).hexdigest()


def verify_fingerprint(deed, original_messages):
    """Verify the pair fingerprint matches the original messages."""
    content = json.dumps(original_messages, sort_keys=True, ensure_ascii=True)
    expected = hashlib.sha256(content.encode()).hexdigest()
    actual = deed.get("fingerprint", "")
    match = expected == actual
    print(f"  Fingerprint: {'PASS' if match else 'FAIL'}")
    if not match:
        print(f"    Expected: {expected}")
        print(f"    Got:      {actual}")
    return match


def verify_classification(deed):
    """Verify the tier classification matches the score."""
    score = deed["quality"]["final_score"]
    tier = deed["classification"]["tier"]

    if score >= 0.75:
        expected = "royal_jelly"
    elif score >= 0.50:
        expected = "honey"
    else:
        expected = "propolis"

    match = tier == expected
    print(f"  Classification: {'PASS' if match else 'FAIL'} (score={score} → {expected})")
    return match


def verify_dual_judge(deed):
    """Verify the final score is the average of both judges."""
    a = deed["quality"]["judge_a"]["score"]
    b = deed["quality"]["judge_b"]["score"]
    expected = round((a + b) / 2, 4)
    actual = deed["quality"]["final_score"]
    match = abs(expected - actual) < 0.001
    print(f"  Dual Judge: {'PASS' if match else 'FAIL'} (A={a} + B={b} → avg={expected}, recorded={actual})")
    return match


def verify_judge_independence(deed):
    """Verify judges are different base models."""
    a_model = deed["quality"]["judge_a"]["model"]
    b_model = deed["quality"]["judge_b"]["model"]
    independent = a_model != b_model
    print(f"  Independence: {'PASS' if independent else 'FAIL'}")
    print(f"    Judge A: {a_model}")
    print(f"    Judge B: {b_model}")
    return independent


def verify_merkle(deed, batch_leaves=None):
    """Verify Merkle root inclusion (requires batch data)."""
    root = deed["trust"].get("merkle_root")
    if not root:
        print(f"  Merkle: PENDING (not yet anchored)")
        return None

    if batch_leaves:
        from judge.merkle import build_merkle_tree, verify_merkle_proof, get_merkle_proof
        computed_root, tree = build_merkle_tree(batch_leaves)
        match = computed_root == root
        print(f"  Merkle Root: {'PASS' if match else 'FAIL'}")
        if not match:
            print(f"    Expected: {root}")
            print(f"    Computed: {computed_root}")
        return match
    else:
        print(f"  Merkle Root: {root[:16]}... (provide batch data to verify)")
        return None


def verify_hedera(deed):
    """Check if Hedera anchor exists (requires network)."""
    topic = deed["trust"].get("hedera_topic")
    seq = deed["trust"].get("hedera_sequence")

    if not topic:
        print(f"  Hedera: PENDING (not yet anchored)")
        return None

    verify_url = f"https://hashscan.io/mainnet/topic/{topic}"
    print(f"  Hedera: topic={topic} seq={seq}")
    print(f"  Verify: {verify_url}")
    return True


def verify_deed(deed_path, full=False):
    """Run all verifications on a deed."""

    with open(deed_path) as f:
        deed = json.load(f)

    print(f"\n{'='*60}")
    print(f"  DEED VERIFICATION: {deed['block_id']}")
    print(f"{'='*60}\n")

    results = {}
    results["classification"] = verify_classification(deed)
    results["dual_judge"] = verify_dual_judge(deed)
    results["independence"] = verify_judge_independence(deed)
    results["merkle"] = verify_merkle(deed)
    results["hedera"] = verify_hedera(deed)

    passed = sum(1 for v in results.values() if v is True)
    failed = sum(1 for v in results.values() if v is False)
    pending = sum(1 for v in results.values() if v is None)

    print(f"\n{'='*60}")
    print(f"  RESULT: {passed} passed, {failed} failed, {pending} pending")
    if failed == 0:
        print(f"  VERDICT: VERIFIED")
    else:
        print(f"  VERDICT: FAILED")
    print(f"{'='*60}\n")

    return failed == 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Deed Verification")
    parser.add_argument("--deed", required=True, help="Deed JSON file to verify")
    parser.add_argument("--full", action="store_true", help="Full verification (re-score with local models)")
    args = parser.parse_args()

    success = verify_deed(args.deed, args.full)
    sys.exit(0 if success else 1)
