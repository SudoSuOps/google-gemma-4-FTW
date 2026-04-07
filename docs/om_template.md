# OFFERING MEMORANDUM
## Defendable AI Training Data — {DOMAIN}

**Prepared by:** Swarm & Bee LLC
**Date:** {DATE}
**Classification:** Confidential — For Qualified Buyers Only

---

## 1. EXECUTIVE SUMMARY

| Field | Value |
|-------|-------|
| **Domain** | {DOMAIN_NAME} |
| **Total Deeded Pairs** | {TOTAL_PAIRS} |
| **Royal Jelly (≥ 0.85)** | {RJ_COUNT} ({RJ_PCT}%) |
| **Honey (0.70–0.84)** | {HONEY_COUNT} ({HONEY_PCT}%) |
| **Propolis (< 0.70)** | {PROPOLIS_COUNT} ({PROPOLIS_PCT}%) |
| **Mean Quality Score** | {MEAN_SCORE} |
| **Deed Coverage** | 100% — every pair titled |
| **Anchor** | Hedera HCS (mainnet) |
| **Verification** | hashscan.io/mainnet/topic/0.0.10291838 |
| **Format** | JSONL (system/user/assistant messages) |
| **License** | Commercial — exclusive or non-exclusive available |

---

## 2. PROPERTY DESCRIPTION

### 2.1 What You're Buying

Each pair in this offering is a **deeded asset** — not raw data. Every pair carries a title deed with five independently verifiable proofs:

1. **Origin** — Which model generated it, on what hardware, using what strategy
2. **Quality** — Dual independent base-model judge scores with reasoning
3. **Process** — Full attempt history (tried, failed, survived)
4. **Economics** — Energy cost, time cost, cost-per-deed trend
5. **Trust** — SHA256 Merkle root anchored to Hedera HCS

### 2.2 Domain Expertise

{DOMAIN_DESCRIPTION}

### 2.3 Specialties / Clusters

{SPECIALTY_BREAKDOWN}

### 2.4 Sample Pair

{SAMPLE_PAIR}

---

## 3. QUALITY ASSURANCE — THE TRIBUNAL

### 3.1 Judging Protocol

Every pair was scored by **two independent base models** — never fine-tuned, never modified from published state:

| Judge | Model | Modified? | Deterministic? |
|-------|-------|-----------|----------------|
| **Judge A** | {JUDGE_A_MODEL} | No | Yes |
| **Judge B** | {JUDGE_B_MODEL} | No | Yes |

### 3.2 Validate the Validator

Every pair was scored **twice per judge** (2-pass validation). If scores drifted more than 0.15 between passes, the pair was **flagged and excluded**. This is not a filter — it's a tribunal.

### 3.3 Classification

| Tier | Score Range | Count | Description |
|------|------------|-------|-------------|
| **Royal Jelly** | ≥ 0.85 | {RJ_COUNT} | Production-ready. Full deed. This ships. |
| **Honey** | 0.70–0.84 | {HONEY_COUNT} | Usable. Improvable. Never discarded. |
| **Propolis** | < 0.70 | {PROPOLIS_COUNT} | Intelligence. Reveals issues before production. |

### 3.4 Score Distribution

{SCORE_HISTOGRAM}

---

## 4. LEGAL DESCRIPTION

### 4.1 Provenance Chain

```
Raw Source → Tribunal (dual judge, 2-pass) → Deed (5 proofs) →
Merkle Batch (SHA256) → Hedera Anchor (mainnet, permanent) →
swarmdeed.eth (ENS, permanent URL)
```

Every step is independently verifiable. The buyer does not need to trust Swarm & Bee.

### 4.2 Verification Instructions

**Step 1: Verify the score**
Run the same scoring prompt against the same base model. The function is deterministic — same input, same output.

**Step 2: Verify the Merkle tree**
Recompute the SHA256 Merkle tree from the batch. The root must match the anchored root.

**Step 3: Verify the Hedera anchor**
Visit hashscan.io/mainnet/topic/0.0.10291838 and find the batch sequence number. The consensus timestamp proves the data existed at that time.

**Step 4: Verify the IPFS content**
Fetch the batch CID from IPFS. The content must hash to the same Merkle leaves.

### 4.3 Title Insurance

The deed IS the insurance. If any proof is invalid:
- Score is wrong → recompute it (deterministic)
- Data was tampered → recompute the Merkle tree (immutable)
- Timestamp is fake → check Hedera (aBFT consensus)

### 4.4 Encumbrances

None. Clean title. No prior claims on this data. Generated on hardware physically controlled by Swarm & Bee LLC.

---

## 5. INFRASTRUCTURE

### 5.1 Hardware

| Node | Hardware | Role |
|------|----------|------|
| swarmrails | 2× RTX PRO 6000 Blackwell (96GB) | Training + Judge A |
| whale | RTX 3090 (24GB) | Judge B |
| NAS | Synology DS1525+ RAID1 | Storage (PostgreSQL + MinIO + IPFS) |

### 5.2 Storage

| Layer | Purpose | Location |
|-------|---------|----------|
| PostgreSQL | Hot queries | NAS :5433 |
| MinIO (swarmdeed-finality) | Archival original (versioned) | NAS :9000 |
| IPFS | Public distribution | Swarmrails (47+ peers) |
| Hedera HCS | Trust anchor | Mainnet topic 0.0.10291838 |
| swarmdeed.eth | Permanent URL | ENS → IPFS |

### 5.3 Confidentiality

Your data never leaves hardware physically controlled by Swarm & Bee LLC. No cloud. No shared instances. No third-party processors.

---

## 6. ECONOMICS

| Metric | Value |
|--------|-------|
| **Cost per deed** | ${COST_PER_DEED} |
| **Energy per deed** | {ENERGY_PER_DEED} J |
| **Total cost** | ${TOTAL_COST} |
| **Convergence trend** | {CONVERGENCE_TREND} |

---

## 7. DELIVERY

### 7.1 What You Receive

1. **JSONL file** — All deeded pairs in standard chat format
2. **Deed manifest** — JSON with all 5 proofs per pair
3. **Merkle proofs** — Per-pair Merkle inclusion proofs
4. **Hedera receipt** — Anchor transaction IDs
5. **Verification script** — Run it yourself to validate everything
6. **swarmdeed.eth subdomain** — Your permanent, wallet-verifiable URL

### 7.2 Optional Add-Ons

- **Custom model training** — Fine-tuned LLM on your Royal Jelly data
- **Ongoing management** — We deploy and manage the model on our hardware
- **Epoch updates** — Additional deeded pairs added monthly with convergence tracking

---

## 8. TERMS

Pricing starts with a conversation. Free 50-pair calibration on your data. No commitment.

**Contact:** build@swarmandbee.ai
**Web:** swarmandbee.ai
**Deeds:** swarmdeed.eth.limo
**Graph:** swarmgraph.eth.limo
**Verify:** hashscan.io/mainnet/topic/0.0.10291838

---

*Swarm & Bee LLC — Defendable AI Intelligence*
*D-U-N-S: 138652395 | Licensed FL Brokerage*

*The other teams sell rows. We sell defendable inventory.*
