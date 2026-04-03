# TITLE COMMITMENT
## SwarmTitle Certification

**Commitment #:** TC-{YEAR}-{MMDD}-{SEQ}
**PSA Reference:** PSA-{YEAR}-{MMDD}-{SEQ}
**Permit Reference:** PRM-{YEAR}-{MMDD}-{SEQ}
**Date:** {DATE}

---

## SwarmTitle commits to issue a Title Insurance Certificate upon satisfaction of the following conditions:

### SCHEDULE A — Property Description

| Field | Value |
|-------|-------|
| Domain | {DOMAIN} |
| Pair count | {PAIR_COUNT} |
| Permit | PRM-{YEAR}-{MMDD}-{SEQ} |
| Judge A | {JUDGE_A} (base, unmodified — Hedera seq {SEQ_A}) |
| Judge B | {JUDGE_B} (base, unmodified — Hedera seq {SEQ_B}) |
| Protocol | SwarmProtocol v1.0 — 2-pass validation |

### SCHEDULE B — Requirements

Title insurance will be issued ONLY when all of the following are confirmed:

- [ ] **Permit on file:** SwarmBuilder permit PRM-{YEAR}-{MMDD}-{SEQ} exists with approval signature
- [ ] **Settings match:** Execution settings match frozen flight sheet (SHA256 verified)
- [ ] **Judges base:** Both judge models confirmed unmodified from published state
- [ ] **Judges independent:** Judge A and Judge B are different model families
- [ ] **2-pass validated:** Every scored pair has Pass 1 + Pass 2 scores for both judges
- [ ] **Drift within tolerance:** No scored pair has drift exceeding permitted threshold
- [ ] **Flagged pairs excluded:** All flagged pairs excluded from deed issuance
- [ ] **Merkle trees valid:** Batch Merkle roots recomputed and verified
- [ ] **Hedera anchored:** All Merkle roots submitted to HCS topic with consensus timestamps
- [ ] **Fingerprints match:** Pair fingerprints in deeds match source data SHA256

### SCHEDULE C — Exceptions

Title insurance does NOT cover:
- Downstream model performance (scores measure data quality, not model output)
- Changes in base model behavior due to vendor updates after deed date
- Buyer's use of data outside the licensed domain
- Force majeure affecting Hedera network availability

### EFFECTIVE UPON

This commitment becomes a Title Insurance Certificate when:
1. All Schedule B requirements are satisfied
2. Closing Statement is executed by both parties
3. Payment is received in full
4. Hedera anchor is confirmed with consensus timestamp

---

**SwarmTitle — AI Data Title Company**
A division of Swarm & Bee LLC

Authorized by: _________________________ Date: _____________

---

*swarmtitle.eth — We don't sell data. We prove it's real.*
