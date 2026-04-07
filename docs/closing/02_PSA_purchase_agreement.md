# PURCHASE & SALE AGREEMENT
## Defendable AI Training Data

**Agreement #:** PSA-{YEAR}-{MMDD}-{SEQ}
**LOI Reference:** LOI-{YEAR}-{MMDD}-{SEQ}
**Permit Reference:** PRM-{YEAR}-{MMDD}-{SEQ}
**Date:** {DATE}

---

## 1. PARTIES

**SELLER:** Swarm & Bee LLC, a Florida limited liability company
D-U-N-S: 138652395 | build@swarmandbee.ai

**BUYER:** {CLIENT_NAME}
{CLIENT_ADDRESS}
{CLIENT_CONTACT} | {CLIENT_EMAIL}

---

## 2. PROPERTY DESCRIPTION

The "Property" consists of AI training data pairs certified by SwarmTitle under SwarmProtocol v1.0:

| Field | Description |
|-------|-------------|
| **Domain** | {DOMAIN} |
| **Pair Count** | {PAIR_COUNT} (estimated; final count per Closing Statement) |
| **Classification** | Royal Jelly (≥ 0.85), Honey (0.70–0.84), Propolis (< 0.70) |
| **Format** | JSONL with title deeds |
| **Certification** | SwarmTitle — dual-judge, 2-pass validated, Hedera-anchored |
| **Legal Description** | Per SwarmGraph metes and bounds (swarmgraph.eth) |

---

## 3. PURCHASE PRICE

| Item | Amount |
|------|--------|
| **Base price** | {PAIR_COUNT} pairs × ${COST_PER_DEED}/deed |
| **Title premium** | Included |
| **Total purchase price** | ${TOTAL_PRICE} |
| **Earnest money deposit** | ${DEPOSIT} (due within {DEPOSIT_DAYS} days of execution) |
| **Balance due at closing** | ${BALANCE} |

---

## 4. EARNEST MONEY

Buyer shall deposit ${DEPOSIT} as earnest money within {DEPOSIT_DAYS} business days of PSA execution.

**Deposit method:** {PAYMENT_METHOD}
**Escrow holder:** Swarm & Bee LLC operating account

Earnest money is fully refundable if:
- Calibration results are unsatisfactory (Section 7)
- Seller fails to deliver per Closing Statement
- Title defect discovered by SwarmTitle

Earnest money is NON-refundable if:
- Buyer cancels after permit issuance without cause

---

## 5. PERMIT & FLIGHT SHEET

All work governed by SwarmBuilder permit PRM-{YEAR}-{MMDD}-{SEQ}.

**Frozen settings** (per permit — no changes after execution):

| Parameter | Frozen Value |
|-----------|-------------|
| Judge A | {JUDGE_A} (base, unmodified) |
| Judge B | {JUDGE_B} (base, unmodified) |
| Temperature | {TEMPERATURE} |
| Max tokens | {MAX_TOKENS} |
| Drift threshold | {DRIFT_THRESHOLD} |
| Scoring prompt | {PROMPT_VERSION} (SHA256: {PROMPT_HASH}) |
| Hardware | {HARDWARE_ASSIGNMENT} |

**Flight sheet hash:** {FLIGHT_SHEET_HASH}
Any deviation from frozen settings voids the permit and halts execution.

---

## 6. DUE DILIGENCE PERIOD

Buyer has {DD_DAYS} business days from PSA execution to complete due diligence:

- [ ] Review calibration report (50-pair sample)
- [ ] Verify judge models are base/unmodified
- [ ] Review flight sheet settings
- [ ] Inspect sample deeds and five proofs
- [ ] Verify Hedera topic and prior anchors
- [ ] Review SwarmGraph for domain coverage

Buyer may terminate during due diligence for any reason with full earnest money refund.

---

## 7. CALIBRATION CONTINGENCY

This agreement is contingent on satisfactory calibration:

- Swarm & Bee runs 50-pair calibration under the permitted judges
- Calibration report delivered within 48 hours
- Buyer reviews and approves in writing
- If Buyer disapproves, PSA terminates with full refund

**Minimum acceptable RJ yield:** {MIN_RJ_YIELD}% (or as agreed)

---

## 8. DELIVERABLES

At closing, Buyer receives:

| # | Deliverable | Format |
|---|-------------|--------|
| 1 | **Deeded pairs** | JSONL with embedded title deeds |
| 2 | **Deed manifest** | JSON — all 5 proofs per pair |
| 3 | **Merkle proofs** | JSON — per-pair inclusion proofs |
| 4 | **Hedera receipts** | JSON — anchor transaction IDs + consensus timestamps |
| 5 | **Verification script** | Python — run independently to verify everything |
| 6 | **ENS subdomain** | {CLIENT}.swarmdeed.eth — permanent deed verification URL |
| 7 | **Closing statement** | Variance report: estimated vs delivered |
| 8 | **Title insurance certificate** | SwarmTitle certification with premium coverage |
| 9 | **Permit record** | Frozen flight sheet with approval signature |
| 10 | **Judge calibration certificate** | Calibration snapshot of both judges at time of scoring |

---

## 9. TITLE INSURANCE

SwarmTitle provides title insurance covering:
- Score reproducibility (deterministic function guarantee)
- Merkle tree integrity (recomputable SHA256)
- Hedera anchor validity (consensus timestamp verification)
- Judge calibration accuracy (no undisclosed drift)
- Data integrity (fingerprint match)

**Premium:** Included in per-deed cost
**Duration:** Perpetual (deeds do not expire)
**Claims:** Submit deed ID + evidence → 48-hour resolution

---

## 10. CLOSING

Closing occurs within {CLOSING_DAYS} business days after tribunal completion.

**Closing process:**
1. Tribunal completes all pairs under permit
2. Swarm & Bee prepares Closing Statement (variance report)
3. SwarmTitle verifies permit compliance and issues certification
4. Merkle roots built and anchored to Hedera
5. Buyer reviews Closing Statement
6. Balance payment received
7. Deliverables transferred to Buyer
8. ENS subdomain assigned: {CLIENT}.swarmdeed.eth
9. Closing confirmed — deal recorded

---

## 11. REPRESENTATIONS & WARRANTIES

**Seller represents:**
- All pairs were scored using the permitted base models, unmodified
- All settings match the frozen flight sheet
- No fine-tuned models were used as judges
- Data was processed on hardware physically controlled by Seller
- No third-party cloud processing occurred
- Hedera anchors are authentic and verifiable

**Buyer acknowledges:**
- AI training data quality is assessed by deterministic scoring, not human opinion
- Classification tiers (Royal Jelly/Honey/Propolis) are based on the scoring function, not guarantees of downstream model performance
- Buyer has the right to independently verify all deeds using the provided verification script

---

## 12. WARRANTY PERIOD

Seller provides a {WARRANTY_DAYS}-day post-closing warranty:
- If any deed's score cannot be reproduced using the permitted settings, Seller re-scores the affected batch at no cost
- If Merkle root doesn't verify, Seller re-anchors at no cost
- Claims must include deed ID and evidence of non-reproducibility

---

## 13. CONFIDENTIALITY

- Buyer's data never leaves hardware controlled by Seller
- No cloud processing, no shared instances
- Seller does not retain copies of Buyer's raw data after delivery
- Deed records (without pair content) are retained for provenance chain

---

## 14. GOVERNING LAW

This agreement is governed by the laws of the State of Florida.

---

## 15. SIGNATURES

**SELLER: Swarm & Bee LLC**

Name: _________________________ Date: _____________

Title: _________________________ Signature: _____________


**BUYER: {CLIENT_NAME}**

Name: _________________________ Date: _____________

Title: _________________________ Signature: _____________

---

*Swarm & Bee LLC — Defendable AI Intelligence*
*SwarmBuilder: swarmbuilder.eth | SwarmTitle: swarmtitle.eth | SwarmDeed: swarmdeed.eth*
