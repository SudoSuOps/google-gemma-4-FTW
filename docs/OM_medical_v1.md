# OFFERING MEMORANDUM
## Defendable AI Training Data — MEDICAL

**Prepared by:** Swarm & Bee LLC
**Date:** April 03, 2026
**Classification:** Confidential — For Qualified Buyers Only

---

## 1. EXECUTIVE SUMMARY

| Field | Value |
|-------|-------|
| **Domain** | Medical |
| **Total Deeded Pairs** | 417,136 |
| **Royal Jelly (≥ 0.85)** | 229,424 (55%) |
| **Honey (0.70–0.84)** | 125,140 (30%) |
| **Propolis (< 0.70)** | 62,572 (15%) |
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

This offering contains **clinical intelligence across 61 medical specialties** —
internal medicine (98K pairs), surgery (43K), neurology (38K), obstetrics (28K), pharmacology (22K),
and 56 additional specialties. Pairs include MRI/imaging interpretation, differential diagnosis,
drug interaction analysis, surgical planning, and evidence-based treatment recommendations.

Target buyers: Health tech companies, clinical decision support systems, medical education platforms,
telemedicine providers, pharmaceutical R&D, hospital IT departments.

### 2.3 Specialties / Clusters

| Specialty | Pairs |
|-----------|-------|
| internal-medicine | 98,986 |
| surgery | 43,051 |
| neurology | 38,360 |
| obstetrics | 27,531 |
| womens-health | 23,825 |
| pharmacology | 22,085 |
| cell-biology | 21,130 |
| pathology | 17,402 |
| immunology | 14,264 |
| pediatrics | 14,149 |
| psychiatry | 13,580 |
| cardiology | 13,166 |
| histology | 13,104 |
| physiology | 13,064 |
| anatomy | 9,065 |


### 2.4 Sample Pair

**[SYSTEM]**
```
You are a board-certified neuroradiologist. Interpret imaging findings systematically by anatomical level. Report disc morphology, signal characteristics, neural compromise, and clinical correlation. Use structured reporting format....
```

**[USER]**
```
[MRI IMAGE: Sagittal T2-weighted lumbar spine]

Patient Information:
- Age: 77
- Sex: F
- Primary symptoms: axial low back pain without radicular symptoms
- Onset/context: after repetitive bending
- Examination: limited lumbar range of motion
- Relevant history: osteoarthritis, previous lumbar surge...
```

**[ASSISTANT]**
```
## Findings

### Lumbar Spine Levels (L1-L5/S1)
#### Level L4-L5
- **Disc Morphology and Signal:** The L4-L5 intervertebral disc demonstrates a moderate degree of intradiscal signal intensity increase, suggestive of mild to moderate degenerative disc disease. There is no evidence of disc herniation....
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
| **Royal Jelly** | ≥ 0.85 | 229,424 | Production-ready. Full deed. This ships. |
| **Honey** | 0.70–0.84 | 125,140 | Usable. Improvable. Never discarded. |
| **Propolis** | < 0.70 | 62,572 | Intelligence. Reveals issues before production. |

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
| **Total cost** | $2,085.68 |
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
