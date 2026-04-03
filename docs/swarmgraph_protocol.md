# SwarmGraph Protocol Specification v1.0

**Swarm & Bee LLC — Defendable AI Intelligence**

> Context graphs will be to the 2030s what databases were to the 2000s.
> SwarmGraph is the context graph for AI training data.

---

## 1. What Is SwarmGraph

SwarmGraph is a directed acyclic graph (DAG) that maps the complete decision history
of every training pair from raw data to deployed model. Every node is a decision.
Every edge is provenance. Every anchor is permanent.

A database tells you what exists. A graph tells you **why it exists.**

A deed tells you a pair is Royal Jelly. SwarmGraph tells you:
- Who judged it (and their calibration history)
- What hardware scored it (and the cost)
- Which batch it anchored with (and the Merkle proof)
- Which writer model trained on it (and that model's convergence)
- Whether re-scoring improved or degraded it (and by how much)

Pull any node. The full decision trace unwinds back to raw data.

---

## 2. The Problem SwarmGraph Solves

### The Hierarchy Tax

In traditional AI pipelines, data flows through human hierarchies:

```
Raw Data → Curator → Reviewer → Manager → Training Pipeline → Model
              ↓          ↓          ↓
          (compressed) (filtered) (summarized)
```

At every layer, information is lossy-compressed. By the time data reaches the model,
nobody can trace why any particular pair survived. The hierarchy is high-latency,
low-bandwidth, and lossy.

### The SwarmGraph Alternative

```
Raw Data → Tribunal (deterministic) → Deed (lossless) → Graph (permanent)
                                                              ↓
                                                    Full decision trace
                                                    Zero compression
                                                    Any node → raw data
```

No managers. No summaries. No lossy compression. The graph preserves the full
reasoning chain from observation to action. Every participant at the edge
gets the complete picture.

---

## 3. Graph Schema

### 3.1 Node Types

```
┌─────────────────────────────────────────────────────────────┐
│                      NODE TYPES                             │
├──────────────┬──────────────────────────────────────────────┤
│ PAIR         │ A training pair (system/user/assistant)      │
│ DEED         │ Title deed with 5 proofs                     │
│ JUDGE        │ A judge model instance (base, unmodified)    │
│ WRITER       │ A writer model (fine-tuned on Royal Jelly)   │
│ BLOCK        │ A SwarmChain validation block                │
│ BATCH        │ A Merkle batch (group of deeds)              │
│ ANCHOR       │ A Hedera HCS anchor point                    │
│ DOMAIN       │ A subject domain (medical, CRE, aviation...) │
│ SILICON      │ A hardware node (GPU, Jetson, Zima...)       │
│ EPOCH        │ A training epoch / convergence window        │
│ CALIBRATION  │ A judge calibration snapshot                 │
└──────────────┴──────────────────────────────────────────────┘
```

### 3.2 Edge Types

```
┌─────────────────────────────────────────────────────────────┐
│                      EDGE TYPES                             │
├────────────────────┬────────────────────────────────────────┤
│ SCORED_BY          │ Pair → Judge (score, reasoning, pass)  │
│ DEEDED_AS          │ Pair → Deed (tier, sealed_at)          │
│ PRODUCED_BY        │ Pair → Writer (generation context)     │
│ IN_BLOCK           │ Deed → Block (position, timestamp)     │
│ IN_BATCH           │ Deed → Batch (leaf_index)              │
│ ANCHORED_TO        │ Batch → Anchor (merkle_root, tx_id)    │
│ TRAINED_ON         │ Writer → Deed (which data trained it)  │
│ RAN_ON             │ Judge/Writer → Silicon (hardware used)  │
│ BELONGS_TO         │ Pair → Domain (specialty, cluster)     │
│ IMPROVED_FROM      │ Deed → Deed (re-score lineage)         │
│ CONVERGES_WITH     │ Epoch → Epoch (trend direction)        │
│ CALIBRATED_AT      │ Judge → Calibration (drift snapshot)   │
│ COSTS              │ Deed → Silicon (energy, time, USD)     │
└────────────────────┴────────────────────────────────────────┘
```

### 3.3 Node Properties

#### PAIR Node
```json
{
  "type": "PAIR",
  "id": "pair_sha256_fingerprint",
  "messages": [...],
  "char_count": 10835,
  "token_count": 2717,
  "created_at": "2026-04-02T00:00:00Z"
}
```

#### DEED Node
```json
{
  "type": "DEED",
  "id": "SB-2026-0402-00001",
  "final_score": 0.91,
  "tier": "royal_jelly",
  "pass_1_score": 0.89,
  "pass_2_score": 0.93,
  "max_drift": 0.04,
  "validated": true,
  "sealed_at": "2026-04-02T14:22:08Z"
}
```

#### JUDGE Node
```json
{
  "type": "JUDGE",
  "id": "gemma-4-e2b-base",
  "model": "google/gemma-4-E2B-it",
  "modified": false,
  "deterministic": true,
  "total_scores": 45000,
  "mean_score": 0.72,
  "calibration_drift": 0.003
}
```

#### SILICON Node
```json
{
  "type": "SILICON",
  "id": "jetson-orin-sigedge",
  "hardware": "NVIDIA Jetson Orin Nano 8GB",
  "arch": "Ampere",
  "power_watts": 6,
  "location": "edge",
  "cost_per_hour": 0.001
}
```

#### ANCHOR Node
```json
{
  "type": "ANCHOR",
  "id": "hedera_0.0.10291838_seq_17",
  "topic": "0.0.10291838",
  "sequence": 17,
  "merkle_root": "a3f8c1d9...",
  "consensus_timestamp": "2026-04-02T14:22:08Z",
  "verify_url": "https://hashscan.io/mainnet/topic/0.0.10291838"
}
```

---

## 4. Graph Traversals (The Value)

### 4.1 Model Provenance
**"Prove this model was trained on clean data."**

```
Query: WRITER("swarmgrant-gemma4-31b")
       → TRAINED_ON → DEED[tier=royal_jelly]
       → SCORED_BY → JUDGE[modified=false]
       → ANCHORED_TO → ANCHOR[topic=0.0.10291838]

Result: Complete chain from model → verified deeds → base judges → Hedera
```

### 4.2 Domain Convergence
**"Which domain produces the most Royal Jelly per pair?"**

```
Query: GROUP BY DOMAIN
       → COUNT(DEED[tier=royal_jelly]) / COUNT(PAIR)

Result:
  grants:    72% Royal Jelly yield
  aviation:  68% Royal Jelly yield
  cre:       61% Royal Jelly yield
  medical:   54% Royal Jelly yield
```

### 4.3 Judge Calibration Drift
**"Is Judge A scoring harder over time?"**

```
Query: JUDGE("gemma-4-e2b")
       → CALIBRATED_AT → CALIBRATION[ordered by time]
       → COMPARE mean_score across windows

Result: Judge A mean drifted 0.71 → 0.69 over 10K pairs (0.003/window)
        Action: Within tolerance. No recalibration needed.
```

### 4.4 Cost Optimization
**"What's the cheapest path to 10K Royal Jelly medical pairs?"**

```
Query: DOMAIN("medical")
       → DEED[tier=royal_jelly]
       → COSTS → SILICON
       → OPTIMIZE(cost_usd, target=10000)

Result:
  Option A: Jetson fleet (6W each) — $48, 72 hours
  Option B: RTX 3090 single — $31, 18 hours
  Option C: RTX PRO 6000 — $22, 8 hours
```

### 4.5 Data Lineage
**"This pair scored 0.91. Show me everything."**

```
Query: PAIR("sha256_fingerprint")
       → SCORED_BY → JUDGE A (0.89, reasoning: "...")
       → SCORED_BY → JUDGE B (0.93, reasoning: "...")
       → DEEDED_AS → DEED("SB-2026-0402-00847")
       → IN_BATCH → BATCH(merkle_root: "a3f8...")
       → ANCHORED_TO → ANCHOR(hedera seq 17)
       → PRODUCED_BY → WRITER("gemma-4-31b")
       → RAN_ON → SILICON("swarmrails-gpu0")
       → BELONGS_TO → DOMAIN("cre")

Full trace: raw pair → dual judge → deed → Merkle → Hedera
            Hardware: Blackwell 96GB
            Cost: $0.005
            Time: 4.2 seconds
```

### 4.6 Validate the Validator
**"Prove the judges are independent and consistent."**

```
Query: ALL DEED nodes
       → GROUP BY JUDGE pair
       → COMPUTE correlation(judge_a.score, judge_b.score)
       → COMPUTE mean(max_drift) across 2-pass validation
       → VERIFY judge_a.model != judge_b.model

Result:
  Judge correlation: 0.84 (high agreement, not identical — independent)
  Mean 2-pass drift: 0.032 (highly reproducible)
  Independence: VERIFIED (Gemma E2B ≠ Qwen 2.5 9B)
```

---

## 5. How SwarmGraph Integrates

```
┌──────────────────────────────────────────────────────┐
│                    SwarmOS                            │
│            (lifecycle management)                    │
│                                                      │
│  ┌────────────┐  ┌────────────┐  ┌────────────────┐ │
│  │ SwarmChain │  │ SwarmGraph │  │  Glass Wall    │ │
│  │ (tribunal) │→ │ (context)  │→ │  (visibility)  │ │
│  │            │  │            │  │                │ │
│  │ Score      │  │ Map        │  │ Show           │ │
│  │ Validate   │  │ Connect    │  │ Prove          │ │
│  │ Classify   │  │ Traverse   │  │ Deliver        │ │
│  └────────────┘  └────────────┘  └────────────────┘ │
│         ↓               ↓               ↓           │
│  ┌─────────────────────────────────────────────────┐ │
│  │              Hedera HCS (trust)                 │ │
│  │       Immutable. Public. Permanent.             │ │
│  └─────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────┘
```

- **SwarmChain** produces the raw decisions (scores, deeds, blocks)
- **SwarmGraph** maps the relationships between all decisions
- **Glass Wall** renders the graph for client visibility
- **Hedera** anchors the graph state permanently

---

## 6. Properties of SwarmGraph

| Property | Description |
|----------|-------------|
| **Append-only** | Nodes and edges are added, never deleted. History is permanent. |
| **Deterministic** | Any node can be recomputed from its inputs. Run the judge, get the same score. |
| **Lossless** | No compression between layers. Full reasoning preserved at every node. |
| **Anchored** | Graph state is periodically Merkle-rooted and anchored to Hedera. |
| **Traversable** | Any node → full provenance chain in either direction. |
| **Domain-agnostic** | Same schema for medical, CRE, aviation, grants, or any new domain. |
| **Edge-native** | Graph can be built and queried on a $200 Jetson. Not cloud-dependent. |

---

## 7. SwarmGraph vs. Traditional Approaches

| | Database | RAG Index | SwarmGraph |
|--|----------|-----------|------------|
| Stores | Records | Embeddings | Decisions |
| Answers | "What exists" | "What's similar" | "Why it exists" |
| Provenance | Foreign keys | None | Full trace |
| Trust | Admin controls | None | Hedera anchor |
| Compression | Normalized | Lossy (embedding) | Lossless |
| Traversal | JOIN queries | Vector search | Graph walk |
| Edge-capable | Sometimes | Rarely | Always |

---

## 8. The Swarm & Bee Advantage

Anyone can build a graph database. The advantage is what goes INTO the graph:

1. **Two-pass validated scores** — not opinions, deterministic
2. **Dual independent judges** — zero shared bias
3. **Title deeds** — formal, structured, immutable
4. **Hedera anchors** — publicly verifiable by anyone
5. **Glass Wall delivery** — clients see the graph, not a summary
6. **1.3M+ nodes** — medical, CRE, aviation, grants

The graph isn't the product. The **trust in the graph** is the product.

---

*SwarmGraph Protocol v1.0 — Swarm & Bee LLC — April 2026*
*The other teams bring models. We bring proof.*
