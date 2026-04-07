# LETTER OF INTENT — FLIGHT SHEET
## SwarmBuilder Permit Application

**Permit Type:** Data Quality Certification
**Prepared by:** Swarm & Bee LLC
**Date:** {DATE}
**LOI #:** LOI-{YEAR}-{MMDD}-{SEQ}

---

## 1. PARTIES

| Role | Entity |
|------|--------|
| **Operator** | Swarm & Bee LLC (D-U-N-S: 138652395) |
| **Client** | {CLIENT_NAME} |
| **Client Contact** | {CLIENT_CONTACT} |
| **Client Email** | {CLIENT_EMAIL} |

---

## 2. SCOPE OF WORK

| Field | Value |
|-------|-------|
| **Domain** | {DOMAIN} |
| **Pair Count** | {PAIR_COUNT} |
| **Data Source** | {DATA_SOURCE} |
| **Data Format** | JSONL (system/user/assistant messages) |
| **Deliverable** | Deeded pairs + Merkle proofs + Hedera anchors + verification script |

---

## 3. JUDGE SELECTION

Client selects two independent base models for the tribunal:

| Judge | Model | State | Selected By |
|-------|-------|-------|-------------|
| **Judge A** | {JUDGE_A_MODEL} | Base — unmodified | {SELECTED_BY} |
| **Judge B** | {JUDGE_B_MODEL} | Base — unmodified | {SELECTED_BY} |

**Protocol:** SwarmProtocol v1.0 — 2-pass validation, drift threshold ≤ 0.15
**Classification:** Royal Jelly ≥ 0.85 | Honey 0.70–0.84 | Propolis < 0.70

---

## 4. HARDWARE ASSIGNMENT

| Node | Hardware | Role |
|------|----------|------|
| {NODE_A} | {HARDWARE_A} | Judge A execution |
| {NODE_B} | {HARDWARE_B} | Judge B execution |
| {NODE_STORAGE} | {HARDWARE_STORAGE} | Data storage (PostgreSQL + MinIO) |

---

## 5. SETTINGS (TO BE FROZEN AT PERMIT)

| Parameter | Value |
|-----------|-------|
| Temperature | {TEMPERATURE} |
| Max tokens | {MAX_TOKENS} |
| Batch size | {BATCH_SIZE} |
| Drift threshold | {DRIFT_THRESHOLD} |
| Scoring prompt | {PROMPT_VERSION} (SHA256: {PROMPT_HASH}) |
| Power cap | {POWER_CAP} per GPU |

---

## 6. ECONOMICS ESTIMATE

| Metric | Estimate |
|--------|----------|
| **Cost per deed** | ${COST_PER_DEED} |
| **Total estimated cost** | ${TOTAL_COST} |
| **Estimated RJ yield** | {EST_RJ_YIELD}% (based on prior calibration) |
| **Estimated timeline** | {EST_TIMELINE} |
| **Title premium** | Included in per-deed cost |

---

## 7. CALIBRATION (FREE — NO COMMITMENT)

Before this LOI becomes binding, Swarm & Bee will run a free 50-pair calibration:

- [ ] Client provides 50 sample pairs
- [ ] Tribunal scores with selected judges
- [ ] Calibration report delivered within 48 hours
- [ ] Client reviews tier breakdown and scores
- [ ] Client approves or modifies judge selection
- [ ] **Only after calibration approval does this LOI proceed to PSA**

---

## 8. INTENT

By signing below, both parties express intent to proceed with the scope described above, contingent on satisfactory calibration results. This LOI is non-binding until executed as a Purchase & Sale Agreement (PSA).

---

### SIGNATURES

**Swarm & Bee LLC — Operator**

Name: _________________________ Date: _____________

Title: _________________________ Signature: _____________


**{CLIENT_NAME} — Client**

Name: _________________________ Date: _____________

Title: _________________________ Signature: _____________

---

*SwarmBuilder Permit Office — swarmbuilder.eth*
*A division of Swarm & Bee LLC*
