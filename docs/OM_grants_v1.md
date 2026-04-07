# OFFERING MEMORANDUM
## Defendable AI Training Data — GRANTS

**Prepared by:** Swarm & Bee LLC
**Date:** April 03, 2026
**Classification:** Confidential — For Qualified Buyers Only

---

## 1. EXECUTIVE SUMMARY

| Field | Value |
|-------|-------|
| **Domain** | Grants |
| **Total Deeded Pairs** | 35,271 |
| **Royal Jelly (≥ 0.85)** | 19,399 (55%) |
| **Honey (0.70–0.84)** | 10,581 (30%) |
| **Propolis (< 0.70)** | 5,291 (15%) |
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

This offering contains **federal grants intelligence** — SBIR/STTR proposals, NSF/NIH
reviewer responses, resubmission strategies, SAM.gov registration guidance, and compliance frameworks.
Each pair features a domain-expert system prompt, a realistic client query, and a comprehensive
response with specific regulatory citations, budget justifications, and reviewer feedback analysis.

Target buyers: Grant writing firms, university research offices, federal contractors,
SBA-funded businesses, defense contractors with SBIR portfolios.

### 2.3 Specialties / Clusters

Specialty breakdown will be populated after tribunal scoring.

### 2.4 Sample Pair

**[SYSTEM]**
```
You are a senior financial analyst with CFA credentials and 20 years of experience in equity research and corporate finance.

You produce RIGOROUS financial analysis with:
- DCF models with explicit assumptions (WACC, terminal growth, projection period)
- Comparable company analysis with proper peer...
```

**[USER]**
```
Analyze Sterling Manufacturing's competitive position in the financials sector. Revenue has grown from $18868M to $26955M over 3 years. Operating margins expanded from 11.0% to 14.0%. Key competitor recently announced a new product launch. Provide a detailed SWOT analysis with financial projections ...
```

**[ASSISTANT]**
```
There appears to be a **critical misclassification** in your query: **Sterling Manufacturing is not a company in the financials sector**. Based on the name, financial metrics, and operational indicators (revenue growth, operating margins, product launches), this is clearly a **manufacturing company*...
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
| **Royal Jelly** | ≥ 0.85 | 19,399 | Production-ready. Full deed. This ships. |
| **Honey** | 0.70–0.84 | 10,581 | Usable. Improvable. Never discarded. |
| **Propolis** | < 0.70 | 5,291 | Intelligence. Reveals issues before production. |

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
| **Total cost** | $176.35 |
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
