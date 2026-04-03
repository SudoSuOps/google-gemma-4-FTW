Run the Swarm & Bee Tribunal on training pairs: $ARGUMENTS

You are the Tribunal operator. You score training pairs with dual independent base-model judges, issue title deeds, and anchor proof to Hedera.

## Workflow

1. Parse the request from $ARGUMENTS to determine:
   - Domain (medical, cre, aviation, grants)
   - Input file path
   - Judge endpoints (default: Gemma 4 E2B + Qwen 2.5 9B)

2. Check if domain data is prepared:
   - Look in `domains/<domain>/tribunal_ready/` for prepared JSONL
   - If not prepared, run `python3 scripts/prepare_domains.py --domain <domain>`

3. Run the tribunal pipeline:
   ```
   python3 judge/score.py --input <input> --output domains/<domain>/scored/scored.jsonl \
     --judge-a-endpoint <endpoint_a> --judge-b-endpoint <endpoint_b>
   ```

4. Generate deeds:
   ```
   python3 judge/deed.py --input domains/<domain>/scored/scored.jsonl \
     --output domains/<domain>/deeds/deeds.jsonl --domain <domain> \
     --extract-rj domains/<domain>/royal_jelly/royal_jelly.jsonl
   ```

5. Build Merkle trees:
   ```
   python3 judge/merkle.py --input domains/<domain>/deeds/deeds.jsonl \
     --output domains/<domain>/deeds/merkle_manifest.json
   ```

6. Report results: tier distribution, Royal Jelly yield, convergence stats.

## Rules
- Judges must be BASE models only. Never fine-tuned. Never modified.
- Every pair scores TWICE (2-pass validation). Drift > 0.15 = flagged.
- The tribunal never shortcuts. Every pair gets the full pipeline.
