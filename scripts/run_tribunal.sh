#!/bin/bash
# ═══════════════════════════════════════════════════════
#  SWARM & BEE — Full Tribunal Pipeline
#  Score → Deed → Merkle → Anchor → Extract RJ → Train
# ═══════════════════════════════════════════════════════
#
# Usage:
#   ./run_tribunal.sh <domain> <input.jsonl> [judge-a-endpoint] [judge-b-endpoint]
#
# Examples:
#   ./run_tribunal.sh medical /data2/medical/medical_pairs.jsonl http://localhost:8085 http://192.168.0.99:8085
#   ./run_tribunal.sh aviation /data2/hive_audit/finalized/aviation_all.jsonl http://localhost:8085 http://192.168.0.99:8085
#   ./run_tribunal.sh grants /home/swarm/swarmwriter-nemotron70b/swarmwriter_full.jsonl http://localhost:8085 http://192.168.0.99:8085

set -e

DOMAIN=${1:?Usage: ./run_tribunal.sh <domain> <input.jsonl> [judge-a-endpoint] [judge-b-endpoint]}
INPUT=${2:?Provide input JSONL path}
JUDGE_A=${3:-"http://localhost:8085"}
JUDGE_B=${4:-"http://192.168.0.99:8085"}

BATCH_ID="SB-$(date +%Y-%m%d)"
OUT_DIR="output/${DOMAIN}/${BATCH_ID}"
mkdir -p "$OUT_DIR"

echo "═══════════════════════════════════════════════════════"
echo "  SWARM & BEE TRIBUNAL"
echo "  Domain:  $DOMAIN"
echo "  Input:   $INPUT"
echo "  Judge A: $JUDGE_A (Gemma 4 E2B base)"
echo "  Judge B: $JUDGE_B (Qwen 2.5 9B base)"
echo "  Batch:   $BATCH_ID"
echo "  Output:  $OUT_DIR"
echo "═══════════════════════════════════════════════════════"

# Step 1: Score all pairs through dual-judge tribunal
echo ""
echo "[1/5] SCORING — Dual independent judges..."
python3 judge/score.py \
    --input "$INPUT" \
    --output "$OUT_DIR/scored.jsonl" \
    --judge-a-endpoint "$JUDGE_A" \
    --judge-b-endpoint "$JUDGE_B" \
    --batch-id "$BATCH_ID"

# Step 2: Generate title deeds
echo ""
echo "[2/5] DEEDS — Generating title deeds..."
python3 judge/deed.py \
    --input "$OUT_DIR/scored.jsonl" \
    --output "$OUT_DIR/deeds.jsonl" \
    --domain "$DOMAIN" \
    --hardware "NVIDIA Blackwell / Ampere" \
    --node "swarmrails" \
    --extract-rj "$OUT_DIR/royal_jelly.jsonl"

# Step 3: Build Merkle trees
echo ""
echo "[3/5] MERKLE — Building SHA256 Merkle trees..."
python3 judge/merkle.py \
    --input "$OUT_DIR/deeds.jsonl" \
    --output "$OUT_DIR/merkle_manifest.json" \
    --batch-size 50

# Step 4: Anchor to Hedera (dry run by default)
echo ""
echo "[4/5] ANCHOR — Hedera HCS anchoring..."
python3 judge/anchor.py \
    --manifest "$OUT_DIR/merkle_manifest.json" \
    --dry-run

echo ""
echo "[5/5] COMPLETE"
echo "═══════════════════════════════════════════════════════"
echo "  Scored:      $OUT_DIR/scored.jsonl"
echo "  Deeds:       $OUT_DIR/deeds.jsonl"
echo "  Royal Jelly: $OUT_DIR/royal_jelly.jsonl"
echo "  Merkle:      $OUT_DIR/merkle_manifest.json"
echo ""
echo "  To anchor for real:"
echo "    python3 judge/anchor.py --manifest $OUT_DIR/merkle_manifest.json"
echo ""
echo "  To train writer on Royal Jelly:"
echo "    python3 writer/train.py --data $OUT_DIR/royal_jelly.jsonl --domain $DOMAIN"
echo "═══════════════════════════════════════════════════════"
