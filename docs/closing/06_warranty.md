# POST-CLOSING WARRANTY
## Score Reproducibility Guarantee

**Warranty #:** WRN-{YEAR}-{MMDD}-{SEQ}
**Closing Reference:** CLS-{YEAR}-{MMDD}-{SEQ}
**Effective Date:** {CLOSING_DATE}
**Expiration Date:** {WARRANTY_EXPIRY} ({WARRANTY_DAYS} days)

---

## COVERAGE

This warranty guarantees that for {WARRANTY_DAYS} days following closing:

### Covered

1. **Score reproducibility** — Running the permitted scoring function with the permitted settings on the permitted base model produces a score within ±0.05 of the recorded score
2. **Merkle integrity** — Recomputing the SHA256 Merkle tree from delivered deed batch produces the same root as the anchored root
3. **Hedera anchor validity** — The anchored Merkle root exists on HCS topic 0.0.10291838 with the recorded consensus timestamp
4. **Fingerprint integrity** — SHA256 fingerprint of delivered pair messages matches the fingerprint recorded in the deed
5. **Judge calibration** — No undisclosed judge drift existed at time of scoring

### NOT Covered

1. Downstream model performance when trained on delivered data
2. Base model behavior changes by the model vendor after the deed date
3. Buyer modifications to delivered data
4. Network issues affecting Hedera gateway availability (data is still on-chain)

---

## CLAIMS PROCESS

1. Buyer submits claim to build@swarmandbee.ai with:
   - Deed ID(s) affected
   - Evidence of non-reproducibility (e.g., re-run output)
   - Permitted settings used in re-run

2. SwarmTitle reviews within 48 hours

3. Remedies:
   - **Score non-reproducible:** Re-score affected batch under original permit at no cost
   - **Merkle mismatch:** Re-anchor corrected Merkle root at no cost
   - **Fingerprint mismatch:** Full batch review + corrected deeds at no cost
   - **Systemic issue (>10% of batch):** Full refund OR complete re-run, buyer's choice

---

## LIMITATION

Total warranty liability shall not exceed the original purchase price of the affected deliverable.

---

**Swarm & Bee LLC**
Authorized by: _________________________ Date: _____________

---

*SwarmTitle — swarmtitle.eth | SwarmDeed — swarmdeed.eth*
