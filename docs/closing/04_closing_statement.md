# CLOSING STATEMENT
## Variance Report — Estimated vs Delivered

**Closing #:** CLS-{YEAR}-{MMDD}-{SEQ}
**PSA Reference:** PSA-{YEAR}-{MMDD}-{SEQ}
**Permit Reference:** PRM-{YEAR}-{MMDD}-{SEQ}
**Date:** {DATE}

---

## 1. PARTIES

| | Entity |
|--|--------|
| **Seller** | Swarm & Bee LLC |
| **Buyer** | {CLIENT_NAME} |

---

## 2. VARIANCE: ESTIMATED vs DELIVERED

| Metric | Estimated (PSA) | Delivered (Actual) | Variance |
|--------|----------------|-------------------|----------|
| **Total pairs** | {EST_PAIRS} | {ACT_PAIRS} | {VAR_PAIRS} |
| **Royal Jelly** | {EST_RJ} ({EST_RJ_PCT}%) | {ACT_RJ} ({ACT_RJ_PCT}%) | {VAR_RJ} |
| **Honey** | {EST_HONEY} | {ACT_HONEY} | {VAR_HONEY} |
| **Propolis** | {EST_PROPOLIS} | {ACT_PROPOLIS} | {VAR_PROPOLIS} |
| **Flagged (excluded)** | {EST_FLAGGED} | {ACT_FLAGGED} | {VAR_FLAGGED} |
| **Mean RJ score** | {EST_MEAN} | {ACT_MEAN} | {VAR_MEAN} |
| **Cost per deed** | ${EST_CPD} | ${ACT_CPD} | ${VAR_CPD} |
| **Total cost** | ${EST_TOTAL} | ${ACT_TOTAL} | ${VAR_TOTAL} |
| **Timeline** | {EST_TIMELINE} | {ACT_TIMELINE} | {VAR_TIMELINE} |
| **Energy consumed** | {EST_ENERGY} | {ACT_ENERGY} | {VAR_ENERGY} |

---

## 3. PERMIT COMPLIANCE

| Check | Status |
|-------|--------|
| Flight sheet hash matches execution | {HASH_MATCH} |
| Judge A model matches permit | {JUDGE_A_MATCH} |
| Judge B model matches permit | {JUDGE_B_MATCH} |
| Temperature matches permit | {TEMP_MATCH} |
| Max tokens matches permit | {TOKENS_MATCH} |
| Drift threshold matches permit | {DRIFT_MATCH} |
| Hardware matches permit | {HW_MATCH} |
| **Overall permit compliance** | **{OVERALL_COMPLIANCE}** |

---

## 4. TITLE CERTIFICATION

| Check | Status |
|-------|--------|
| SwarmTitle Schedule B — all requirements met | {TITLE_STATUS} |
| Title insurance certificate issued | {INSURANCE_ISSUED} |
| Title commitment # | TC-{YEAR}-{MMDD}-{SEQ} |

---

## 5. HEDERA ANCHORING

| Batch | Merkle Root | Hedera Seq | Consensus Timestamp | Status |
|-------|-------------|------------|--------------------|---------| 
| {BATCH_1} | {ROOT_1} | {SEQ_1} | {TS_1} | {STATUS_1} |
| {BATCH_2} | {ROOT_2} | {SEQ_2} | {TS_2} | {STATUS_2} |
| ... | ... | ... | ... | ... |

**Topic:** 0.0.10291838 (POE)
**Verify:** https://hashscan.io/mainnet/topic/0.0.10291838

---

## 6. FINANCIAL SETTLEMENT

| Item | Amount |
|------|--------|
| Total purchase price | ${TOTAL_PRICE} |
| Earnest money applied | (${DEPOSIT}) |
| Adjustment for variance | ${ADJUSTMENT} |
| **Balance due** | **${BALANCE_DUE}** |
| Payment method | {PAYMENT_METHOD} |
| Payment received | {PAYMENT_DATE} |

---

## 7. DELIVERABLES TRANSFERRED

- [ ] Deeded pairs (JSONL) — {FILE_SIZE}
- [ ] Deed manifest (JSON) — {DEED_COUNT} deeds
- [ ] Merkle proofs (JSON) — {BATCH_COUNT} batches
- [ ] Hedera receipts (JSON) — {ANCHOR_COUNT} anchors
- [ ] Verification script (Python)
- [ ] ENS subdomain: {CLIENT}.swarmdeed.eth
- [ ] Closing statement (this document)
- [ ] Title insurance certificate
- [ ] Permit record (frozen flight sheet)
- [ ] Judge calibration certificate

---

## 8. SIGNATURES

**This Closing Statement confirms that all deliverables have been transferred, all payments received, and all title requirements satisfied.**

**SELLER: Swarm & Bee LLC**

Name: _________________________ Date: _____________

Signature: _________________________


**BUYER: {CLIENT_NAME}**

Name: _________________________ Date: _____________

Signature: _________________________


**CERTIFIER: SwarmTitle**

Name: _________________________ Date: _____________

Signature: _________________________

---

*Deal closed. Deeds recorded. Anchored to Hedera. Permanent.*
*Swarm & Bee LLC — swarmbuilder.eth | swarmtitle.eth | swarmdeed.eth*
