# Defendable AI at the Edge — Gemma 4 Competition Entry

**Swarm & Bee** — Kaggle Gemma 4 Competition 2026

> Every training pair scored by an unmodified base model. Every pair titled with an immutable deed. Every batch anchored to Hedera blockchain. The model runs on a $200 box. Verify it yourself.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    CLIENT DATA (any domain)                  │
└──────────────────────────┬──────────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  JUDGE — Gemma 4 E2B (2.3B base, unmodified)               │
│  Hardware: Jetson Orin Nano 8GB ($200, 6W)                  │
│  Role: Score every pair. Issue deed. Never trains.          │
│                                                             │
│  ┌─────────┐  ┌─────────┐  ┌──────────┐  ┌──────────────┐ │
│  │ Score   │→ │  Deed   │→ │  Merkle  │→ │ Hedera HCS   │ │
│  │ (0-1)   │  │ (title) │  │  (root)  │  │ (anchor)     │ │
│  └─────────┘  └─────────┘  └──────────┘  └──────────────┘ │
└──────────────────────────┬──────────────────────────────────┘
                           ▼
              ┌──── Royal Jelly ≥ 0.75 ────┐
              │    (verified pairs only)    │
              └────────────┬───────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  WRITER — Gemma 4 31B (fine-tuned on deeded data)          │
│  Train: RTX PRO 6000 Blackwell (96GB)                      │
│  Deploy: RTX 3090 (Q8) / Jetson (Q4) / Zima+T1000 (Q4)   │
│  Role: Domain specialist. Only eats verified data.         │
└─────────────────────────────────────────────────────────────┘
```

## The Thesis

Everyone else fine-tunes a model. We prove what's in it.

- **Judge never trains** — base Gemma 4 E2B, deterministic, reproducible
- **Writer only eats verified data** — Royal Jelly pairs with full deeds
- **Deeds are universal** — same format whether healthcare, education, or CRE
- **Proof is permanent** — SHA256 Merkle roots on Hedera HCS, publicly verifiable
- **Edge is real** — $200 Jetson runs the judge at 6 watts, offline capable

## Competition Categories

This architecture applies to any category because the deed system is domain-agnostic:

| Category | Application |
|----------|------------|
| **Health & Sciences** | Prove medical training data provenance. Clinic deploys judge on Jetson, verifies locally. |
| **Global Resilience** | Offline-capable edge AI with verifiable data. Works in disaster zones. |
| **Future of Education** | Schools score and validate their own training data on a $200 box. |
| **Digital Equity** | Same verification in Lagos as in Boston. Same deed, same anchor, same proof. |

## Hardware Stack (All NVIDIA Silicon)

| Device | GPU | Role | Power |
|--------|-----|------|-------|
| Jetson Orin Nano | Ampere (8GB) | Judge + edge inference | 6W |
| ZimaBoard + T1000 | Turing (4GB) | Edge inference node | 30W |
| Whale (RTX 3090) | Ampere (24GB) | Writer inference (Q8) | 350W |
| Swarmrails (RTX PRO 6000) | Blackwell (96GB) | Writer training | 300W |

Three generations of NVIDIA silicon: Turing → Ampere → Blackwell.

## Repo Structure

```
google-gemma-4-FTW/
├── judge/                  # Gemma 4 E2B scoring engine
│   ├── score.py            # Deterministic dual-judge scorer
│   ├── deed.py             # Title deed generator
│   ├── merkle.py           # Merkle tree builder
│   └── anchor.py           # Hedera HCS anchoring
│
├── writer/                 # Gemma 4 31B fine-tuning
│   ├── train.py            # QLoRA training script (Blackwell)
│   ├── merge.py            # Adapter merge + GGUF export
│   └── serve.py            # Inference server (vLLM / llama.cpp)
│
├── deeds/                  # Deed specification + examples
│   ├── deed_schema.json    # Deed format specification
│   ├── sample_deed.json    # Example deed with all 5 proofs
│   └── verify.py           # Independent deed verification tool
│
├── edge/                   # Edge deployment
│   ├── jetson/             # Jetson Orin Nano setup
│   │   ├── setup.sh        # Flash + configure
│   │   ├── run_judge.sh    # Launch judge on Jetson
│   │   └── run_writer.sh   # Launch writer (Q4) on Jetson
│   ├── zima/               # ZimaBoard + T1000 setup
│   └── offline.py          # Offline scoring + deferred anchoring
│
├── infrastructure/         # Hardware profiles + Glass Wall docs
│   ├── hardware_profile.md # Full hardware manifest
│   ├── flight_sheet.md     # Template: model assignments, costs
│   ├── calibration.md      # Template: 50-pair test report
│   ├── proof_of_job.md     # Template: projected deliverables
│   └── closing.md          # Template: variance report
│
├── benchmarks/             # Competition benchmarks
│   ├── judge_accuracy.py   # Judge consistency + calibration tests
│   ├── writer_quality.py   # Writer output quality evaluation
│   ├── edge_latency.py     # Inference latency on each device
│   ├── cost_per_deed.py    # Economics: energy + time + hardware
│   └── results/            # Benchmark output data
│
├── scripts/                # Utilities
│   ├── prepare_data.py     # Dataset preparation pipeline
│   ├── export_gguf.sh      # GGUF quantization script
│   └── verify_chain.py     # End-to-end chain verification
│
├── docs/                   # Documentation
│   ├── glass_wall.md       # Glass Wall process specification
│   ├── royal_jelly.md      # Classification system
│   ├── hedera_anchoring.md # Hedera HCS integration
│   └── submission.md       # Competition submission narrative
│
├── LICENSE                 # Apache 2.0
└── README.md               # This file
```

## Glass Wall Process

Modeled on commercial real estate closing. Client approval at every gate.

| # | Document | When | Client Sees |
|---|----------|------|-------------|
| 1 | Hardware Profile | Before anything | GPUs, VRAM, power |
| 2 | Flight Sheet | Before job | Model assignments, costs, settings frozen |
| 3 | Calibration Report | Before pricing | 50-pair test with scores and tier split |
| 4 | Proof of Job | Before launch | Projected cost, timeline, deliverables |
| 5 | Epoch Progress | During job | Gate reports at 25/50/75/100% |
| 6 | Closing Statement | After job | Variance: estimated vs. delivered |
| 7 | Hedera Anchor | After close | SHA256 Merkle root — permanent, public |

## Key Links

- **Live site**: [swarmandbee.ai](https://swarmandbee.ai)
- **SwarmChain**: [swarmchain.eth.limo](https://swarmchain.eth.limo)
- **Hedera topic**: [0.0.10291838](https://hashscan.io/mainnet/topic/0.0.10291838)
- **GitHub**: [SudoSuOps](https://github.com/SudoSuOps)

## Team

**Swarm & Bee** (Swarm & Bee LLC)
- Donovan Mackey — Founder
- West Palm Beach, FL
- Licensed FL Brokerage | D-U-N-S: 138652395
- build@swarmandbee.ai

---

*The other teams bring models. We bring proof.*
