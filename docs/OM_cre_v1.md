# OFFERING MEMORANDUM
## Defendable AI Training Data — CRE

**Prepared by:** Swarm & Bee LLC
**Date:** April 03, 2026
**Classification:** Confidential — For Qualified Buyers Only

---

## 1. EXECUTIVE SUMMARY

| Field | Value |
|-------|-------|
| **Domain** | Cre |
| **Total Deeded Pairs** | 810,097 |
| **Royal Jelly (≥ 0.85)** | 445,553 (55%) |
| **Honey (0.70–0.84)** | 243,029 (30%) |
| **Propolis (< 0.70)** | 121,515 (15%) |
| **Mean Quality Score** | 0.72 (estimated, pre-tribunal) |
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

This offering contains **commercial real estate intelligence** — underwriting analysis,
NOI calculations, cap rate analysis, rent roll evaluation, 1031 exchange strategies,
debt service coverage ratios, and market comparable analysis. Includes multifamily, industrial,
retail, office, cold storage, and medical office specialties.

Target buyers: CRE brokerages, investment firms, REIT operators, lenders,
appraisal firms, property management companies.

### 2.3 Specialties / Clusters

Specialty breakdown will be populated after tribunal scoring.

### 2.4 Sample Pair

**[SYSTEM]**
```
You are SwarmJudge.

You evaluate three AI candidate answers (A, B, C) against a reference.

Determine the best candidate, identify failures, and return ONLY valid JSON.

REQUIRED OUTPUT FORMAT (strict — no other format accepted):
```
{"best_candidate":"A","verdict":"PASS","confidence":0.92,"failure...
```

**[USER]**
```
DOMAIN: cre
TASK_TYPE: lease_reasoning

QUESTION
Analyze the lease for regional food distributor at Technology Park (KCI Airport, Kansas City):

  Tenant: regional food distributor
  Space: 8,000 SF
  Current rent: $6.63/SF (gross)
  Annual rent: $53,040
  Lease term: 2024-11-01 to 2029-11-01
  Esca...
```

**[ASSISTANT]**
```
{"best_candidate": "C", "verdict": "PASS", "confidence": 0.92, "failure_modes": {"A": "numeric_error", "B": "hallucination", "C": "none"}, "reasons": ["Candidate A contains arithmetic errors and wrong calculations", "Candidate B fabricates data sources and inflates figures", "Candidate C accurately ...
```



---

## 3. QUALITY ASSURANCE — THE TRIBUNAL

### 3.1 Judging Protocol

Every pair was scored by **two independent base models** — never fine-tuned, never modified from published state:

| Judge | Model | Modified? | Deterministic? |
|-------|-------|-----------|----------------|
| **Judge A** | google/gemma-3-12b (base, unmodified) | No | Yes |
| **Judge B** | Qwen/Qwen2.5-7B-Instruct (base, unmodified) | No | Yes |

### 3.2 Validate the Validator

Every pair was scored **twice per judge** (2-pass validation). If scores drifted more than 0.15 between passes, the pair was **flagged and excluded**. This is not a filter — it's a tribunal.

### 3.3 Classification

| Tier | Score Range | Count | Description |
|------|------------|-------|-------------|
| **Royal Jelly** | ≥ 0.85 | 445,553 | Production-ready. Full deed. This ships. |
| **Honey** | 0.70–0.84 | 243,029 | Usable. Improvable. Never discarded. |
| **Propolis** | < 0.70 | 121,515 | Intelligence. Reveals issues before production. |

### 3.4 Score Distribution

Score distribution chart will be generated after tribunal scoring.

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
| **Cost per deed** | $0.005 |
| **Energy per deed** | 1,260 J |
| **Total cost** | $4,050.49 |
| **Convergence trend** | Will be measured during tribunal run. |

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
