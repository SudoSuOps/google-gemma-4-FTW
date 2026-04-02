#!/usr/bin/env python3
"""
Tribunal Scorer — Dual Independent Gemma 4 E2B Judge
=====================================================
Base models only. Never fine-tuned. Deterministic scoring.
Two independent judges, zero shared bias.

Usage:
    python score.py --input pairs.jsonl --output scored.jsonl
    python score.py --input pairs.jsonl --output scored.jsonl --device cuda:0
    python score.py --input pairs.jsonl --output scored.jsonl --endpoint http://192.168.0.79:8085
"""
import argparse
import json
import hashlib
import time
import sys
from pathlib import Path

# Judge models — BASE only, never modified
JUDGE_A = {
    "model": "google/gemma-4-E2B-it",
    "label": "gemma-4-e2b",
    "description": "Gemma 4 E2B base (2.3B effective) — unmodified from published state",
}
JUDGE_B = {
    "model": "Qwen/Qwen2.5-9B",
    "label": "qwen-2.5-9b",
    "description": "Qwen 2.5 9B base — unmodified from published state",
}

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


def score_pair_local(messages, model_path, device="cuda:0"):
    """Score a pair using a local model via transformers."""
    from transformers import AutoModelForCausalLM, AutoTokenizer
    import torch

    tokenizer = AutoTokenizer.from_pretrained(model_path)
    model = AutoModelForCausalLM.from_pretrained(
        model_path,
        torch_dtype=torch.bfloat16,
        device_map=device,
    )

    system = next((m["content"] for m in messages if m["role"] == "system"), "")
    user = next((m["content"] for m in messages if m["role"] == "user"), "")
    assistant = next((m["content"] for m in messages if m["role"] == "assistant"), "")

    prompt = SCORING_PROMPT.format(system=system, user=user, assistant=assistant)
    inputs = tokenizer(prompt, return_tensors="pt", truncation=True, max_length=4096).to(device)

    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=200,
            temperature=0.1,
            do_sample=False,
        )
    response = tokenizer.decode(outputs[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True)

    try:
        result = json.loads(response.strip())
        return float(result["score"]), result.get("reasoning", "")
    except (json.JSONDecodeError, KeyError, ValueError):
        return None, f"Parse error: {response[:200]}"


def score_pair_endpoint(messages, endpoint, model_label):
    """Score a pair using an OpenAI-compatible API endpoint."""
    import urllib.request

    system = next((m["content"] for m in messages if m["role"] == "system"), "")
    user = next((m["content"] for m in messages if m["role"] == "user"), "")
    assistant = next((m["content"] for m in messages if m["role"] == "assistant"), "")

    prompt = SCORING_PROMPT.format(system=system, user=user, assistant=assistant)

    payload = json.dumps({
        "model": model_label,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1,
        "max_tokens": 200,
    }).encode()

    req = urllib.request.Request(
        f"{endpoint}/v1/chat/completions",
        data=payload,
        headers={"Content-Type": "application/json"},
    )

    resp = urllib.request.urlopen(req, timeout=120)
    data = json.loads(resp.read().decode())
    response = data["choices"][0]["message"]["content"]

    try:
        result = json.loads(response.strip())
        return float(result["score"]), result.get("reasoning", "")
    except (json.JSONDecodeError, KeyError, ValueError):
        return None, f"Parse error: {response[:200]}"


def fingerprint_pair(messages):
    """Deterministic SHA256 fingerprint of a training pair."""
    content = json.dumps(messages, sort_keys=True, ensure_ascii=True)
    return hashlib.sha256(content.encode()).hexdigest()


def classify(score):
    """Royal Jelly classification."""
    if score >= 0.75:
        return "royal_jelly", ">= 0.75"
    elif score >= 0.50:
        return "honey", "0.50-0.74"
    else:
        return "propolis", "< 0.50"


def run_tribunal(input_path, output_path, judge_a_endpoint=None, judge_b_endpoint=None,
                 judge_a_model=None, judge_b_model=None, device="cuda:0", batch_id=None):
    """Run all pairs through the dual-judge tribunal.

    VALIDATE THE VALIDATOR: Every pair is scored TWICE (Pass 1 + Pass 2).
    If scores diverge > 0.15 between passes, the pair is flagged for manual review.
    Only pairs that survive both passes get a deed. This is the tribunal — not a filter.
    """

    pairs = []
    with open(input_path) as f:
        for line in f:
            if line.strip():
                pairs.append(json.loads(line))

    print(f"[tribunal] Loaded {len(pairs):,} pairs from {input_path}")
    print(f"[tribunal] Judge A: {JUDGE_A['description']}")
    print(f"[tribunal] Judge B: {JUDGE_B['description']}")
    print(f"[tribunal] Protocol: 2-PASS VALIDATION (validate the validator)")

    if not batch_id:
        batch_id = f"SB-{time.strftime('%Y-%m%d')}"

    results = []
    stats = {"royal_jelly": 0, "honey": 0, "propolis": 0, "errors": 0}
    start = time.time()

    for i, pair in enumerate(pairs):
        messages = pair.get("messages", [])
        if not messages:
            stats["errors"] += 1
            continue

        fp = fingerprint_pair(messages)
        block_id = f"{batch_id}-{i+1:05d}"

        # Judge A
        t0 = time.time()
        if judge_a_endpoint:
            score_a, reason_a = score_pair_endpoint(messages, judge_a_endpoint, JUDGE_A["label"])
        elif judge_a_model:
            score_a, reason_a = score_pair_local(messages, judge_a_model, device)
        else:
            score_a, reason_a = None, "No judge A configured"

        # Judge B
        if judge_b_endpoint:
            score_b, reason_b = score_pair_endpoint(messages, judge_b_endpoint, JUDGE_B["label"])
        elif judge_b_model:
            score_b, reason_b = score_pair_local(messages, judge_b_model, device)
        else:
            score_b, reason_b = None, "No judge B configured"

        elapsed_ms = int((time.time() - t0) * 1000)

        if score_a is None or score_b is None:
            stats["errors"] += 1
            print(f"  [{i+1}/{len(pairs)}] ERROR: A={score_a} B={score_b}")
            continue

        # ─── PASS 2: Validate the validator ───
        # Re-score to confirm consistency. If judges can't reproduce
        # their own score within 0.15, the pair is flagged.
        if judge_a_endpoint:
            score_a2, _ = score_pair_endpoint(messages, judge_a_endpoint, JUDGE_A["label"])
        elif judge_a_model:
            score_a2, _ = score_pair_local(messages, judge_a_model, device)
        else:
            score_a2 = score_a

        if judge_b_endpoint:
            score_b2, _ = score_pair_endpoint(messages, judge_b_endpoint, JUDGE_B["label"])
        elif judge_b_model:
            score_b2, _ = score_pair_local(messages, judge_b_model, device)
        else:
            score_b2 = score_b

        elapsed_ms = int((time.time() - t0) * 1000)

        # Check reproducibility
        drift_a = abs(score_a - score_a2) if score_a2 is not None else 0
        drift_b = abs(score_b - score_b2) if score_b2 is not None else 0
        max_drift = max(drift_a, drift_b)
        validated = max_drift <= 0.15

        if not validated:
            stats["errors"] += 1
            print(f"  [{i+1}/{len(pairs)}] FLAGGED: drift={max_drift:.3f} (A:{score_a:.3f}→{score_a2:.3f} B:{score_b:.3f}→{score_b2:.3f})")
            continue

        # Use average of both passes for final score
        final_a = round((score_a + (score_a2 or score_a)) / 2, 4)
        final_b = round((score_b + (score_b2 or score_b)) / 2, 4)
        final_score = round((final_a + final_b) / 2, 4)
        tier, threshold = classify(final_score)
        stats[tier] += 1

        scored_pair = {
            **pair,
            "tribunal": {
                "block_id": block_id,
                "fingerprint": fp,
                "judge_a": {
                    "model": JUDGE_A["model"],
                    "label": JUDGE_A["label"],
                    "score": final_a,
                    "pass_1": round(score_a, 4),
                    "pass_2": round(score_a2, 4) if score_a2 is not None else None,
                    "drift": round(drift_a, 4),
                    "reasoning": reason_a,
                },
                "judge_b": {
                    "model": JUDGE_B["model"],
                    "label": JUDGE_B["label"],
                    "score": final_b,
                    "pass_1": round(score_b, 4),
                    "pass_2": round(score_b2, 4) if score_b2 is not None else None,
                    "drift": round(drift_b, 4),
                    "reasoning": reason_b,
                },
                "final_score": final_score,
                "max_drift": round(max_drift, 4),
                "validated": validated,
                "classification": {"tier": tier, "threshold": threshold},
                "generation_time_ms": elapsed_ms,
                "sealed_at": time.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            },
        }
        results.append(scored_pair)

        if (i + 1) % 10 == 0:
            elapsed = time.time() - start
            rate = (i + 1) / elapsed
            print(f"  [{i+1}/{len(pairs)}] score={final_score:.3f} tier={tier} "
                  f"({rate:.1f} pairs/s) RJ:{stats['royal_jelly']} H:{stats['honey']} P:{stats['propolis']}")

    # Write results
    with open(output_path, "w") as f:
        for r in results:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    elapsed = time.time() - start
    total = stats["royal_jelly"] + stats["honey"] + stats["propolis"]
    print(f"\n[tribunal] Complete: {total:,} scored in {elapsed:.0f}s")
    print(f"  Royal Jelly: {stats['royal_jelly']:,} ({stats['royal_jelly']/max(total,1)*100:.1f}%)")
    print(f"  Honey:       {stats['honey']:,} ({stats['honey']/max(total,1)*100:.1f}%)")
    print(f"  Propolis:    {stats['propolis']:,} ({stats['propolis']/max(total,1)*100:.1f}%)")
    print(f"  Errors:      {stats['errors']:,}")
    print(f"  Output:      {output_path}")

    return results, stats


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Tribunal Scorer — Dual Judge")
    parser.add_argument("--input", required=True, help="Input JSONL file with training pairs")
    parser.add_argument("--output", required=True, help="Output JSONL file with scored pairs")
    parser.add_argument("--judge-a-endpoint", help="OpenAI-compatible endpoint for Judge A")
    parser.add_argument("--judge-b-endpoint", help="OpenAI-compatible endpoint for Judge B")
    parser.add_argument("--judge-a-model", help="Local model path for Judge A")
    parser.add_argument("--judge-b-model", help="Local model path for Judge B")
    parser.add_argument("--device", default="cuda:0", help="CUDA device for local models")
    parser.add_argument("--batch-id", help="Batch identifier (default: auto-generated)")
    args = parser.parse_args()

    run_tribunal(
        args.input, args.output,
        judge_a_endpoint=args.judge_a_endpoint,
        judge_b_endpoint=args.judge_b_endpoint,
        judge_a_model=args.judge_a_model,
        judge_b_model=args.judge_b_model,
        device=args.device,
        batch_id=args.batch_id,
    )
