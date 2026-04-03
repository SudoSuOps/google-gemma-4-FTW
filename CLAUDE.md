# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

Swarm & Bee's Kaggle Gemma 4 competition entry AND the full SwarmProtocol production stack. Dual-judge AI training data quality scoring with blockchain-anchored title deeds. CRE title insurance model applied to AI data.

## Standing Rules — NON-NEGOTIABLE

1. **NEVER CLAIM DONE WITHOUT VERIFICATION** — After writing a file, read it back. After running a script, show actual output. After a data op, show row counts.
2. **CLOSE ALL LOOPS** — No TODOs without a plan, no broken imports, no dead env vars. Document loose ends in OPEN_ITEMS.md.
3. **NEVER TOUCH CORPUS WITHOUT AUDIT** — Run validators before any corpus write op. Show counts before and after.
4. **MODULAR FIRST** — Every service is its own module. No monolith sprawl.
5. **HEDERA ANCHORING IS PRODUCTION-GRADE** — Not mocked in prod. Test against testnet, deploy to mainnet after verification.
6. **DEEDS ARE Q&A PAIRS** — Deeds are written by a base model (12B+), NOT generated as JSON metadata by code. If a deed doesn't have model-written VERDICT/SCORE/CLASSIFICATION/REASONING, it's not a deed.
7. **9B JUDGES, 12B WRITES** — Judges are 9B class base models. Deed writer is 12B+. Never use models smaller than 12B for deed writing. Small models produce boilerplate that fails inspector validation.
8. **QUALITY OVER SPEED** — Especially on medical. Never overload the bin. 1,000 pairs at a time. Record deeds before loading more.

## Architecture

```
SwarmProtocol (spec)
└── SwarmOS (lifecycle)
    ├── SwarmChain (tribunal execution)
    │   ├── Defendable (scoring algorithm)
    │   ├── SwarmGraph (context graph / metes & bounds)
    │   └── SwarmDeed (deed recording / finality)
    └── SwarmBuild (permits / flight sheets)

SwarmTitle (independent certifier — separate from production)
SwarmShop (marketplace)
SwarmTribunal MCP (Tribunal-as-a-Service)
```

## Key Modules

- **`judge/`** — Dual-judge scorer (`score.py`), deed generator (`deed.py`), Merkle tree builder (`merkle.py`), Hedera anchor (`anchor.py`)
- **`swarmchain/`** — Bin queue (`bin.py`), deed writer (`deed_writer.py`), Hedera anchoring (`hedera_anchor.js`), judge registration (`register_judges.js`)
- **`swarmgraph/`** — Graph engine (`graph.py`), node/edge types (`nodes.py`), CLI (`cli.py`), UI (`ui.html`)
- **`writer/`** — Gemma 4 31B QLoRA training (`train.py`), adapter merge + GGUF export (`merge.py`)
- **`mcp/`** — SwarmTribunal MCP server (`swarmtribunal-mcp.py`)
- **`ops/`** — Real-time API (`api.py`), ENS site builds (`ipfs-sites/`)
- **`database/`** — PostgreSQL schema (`init.sql`, `views.sql`), sync engine (`sync.py`), deed pipeline (`deed_pipeline.py`)
- **`scripts/`** — Domain preparation (`prepare_domains.py`), OM generation (`generate_om.py`), tribunal orchestrator (`run_tribunal.sh`)
- **`docs/closing/`** — CRE transaction templates: LOI, PSA, title commitment, closing statement, calibration cert, warranty

## Data Pipeline

```
Pairs → Bin (PostgreSQL) → Tribunal (dual 9B judge, 2-pass) →
Deed Writer (12B gemma3) → Merkle (SHA256, batches of 50) →
MinIO (archive) → PostgreSQL (record) → IPFS (public) →
Hedera HCS (anchor) → swarmdeed.eth (permanent URL)
```

## Infrastructure

- **GPU 0**: RTX PRO 6000 Blackwell 96GB — writer training (300W cap)
- **GPU 1**: RTX PRO 6000 Blackwell 96GB — judges + deed writer via ollama
- **Whale**: RTX 3090 24GB at 192.168.0.99 — Judge B (qwen2.5:7b, `OLLAMA_HOST=0.0.0.0`)
- **NAS**: Synology DS1525+ at 192.168.0.102 — PostgreSQL (:5433), MinIO (:9000), IPFS
- **Zima**: 192.168.0.173 — swarmandbee.ai (Cloudflare Tunnel + nginx + Resend form handler)
- **Hedera**: Mainnet operator 0.0.10291827, 4 HCS topics (block/receipt/event/POE), 7 registered agents

## Database

PostgreSQL 17 + pgvector on NAS at `192.168.0.102:5433`, db: `swarmgraph`, user: `swarm`.

Key tables: `pairs` (1.3M), `deeds`, `bin` (tribunal queue), `tribunal_scores`, `graph_edges`, `judges`, `writers`, `silicon`, `domains`, `anchors`, `batches`, `audit_log`, `convergence`, `calibrations`, `training_log`.

Auto-triggers on deed insert create graph edges + audit entries.

## Commands

```bash
# Tribunal — load pairs and run judges
DATABASE_URL="postgresql://swarm:swarmandbee2026@192.168.0.102:5433/swarmgraph" \
  python3 swarmchain/bin.py load --domain medical --limit 1000
DATABASE_URL="postgresql://swarm:swarmandbee2026@192.168.0.102:5433/swarmgraph" \
  JUDGE_A="http://localhost:11434" JUDGE_B="http://192.168.0.99:11434" \
  python3 swarmchain/bin.py run --batch 10 --continuous

# Deed writer (12B only)
DATABASE_URL="postgresql://swarm:swarmandbee2026@192.168.0.102:5433/swarmgraph" \
  DEED_WRITER="http://localhost:11434" DEED_WRITER_MODEL="gemma3:12b" \
  python3 swarmchain/deed_writer.py --output domains/medical/deeds/ --model gemma3:12b --continuous

# Inspector
python3 /home/swarm/Swarm-Inspector/inspector.py --full
python3 /home/swarm/Swarm-Inspector/inspect_deeds.py --deed-file domains/medical/deeds/medical_deeds_written.jsonl --sample 10

# Merkle trees
python3 judge/merkle.py --input domains/medical/deeds/deeds.jsonl --output merkle_manifest.json

# Hedera anchor
node swarmchain/hedera_anchor.js batch merkle_manifest.json

# Ops API
python3 ops/api.py --port 9090

# Domain preparation
python3 scripts/prepare_domains.py --domain all

# DB sync
DATABASE_URL="..." python3 database/sync.py --domain all --bulk

# SwarmGraph CLI
python3 -m swarmgraph.cli summary
python3 -m swarmgraph.cli provenance --node deed:SB-2026-0403-00001

# IPFS pin
IPFS_PATH=/tmp/ipfs-swarmrails ipfs add -r -Q /path/to/site/
```

## ENS Domains (13 live on IPFS)

swarmbuilder.eth, swarmtitle.eth, swarmshop.eth, swarmdeed.eth, swarmgraph.eth, swarmchain.eth, swarmprotocol.eth, defendable.eth, swarmos.eth, swarmdev.eth, swarmledger.eth, swarmepoch.eth, swarmenergy.eth

To update: build site → `ipfs add -r -Q` → set content hash in ENS manager.

## Hedera Topics

| Topic | ID | Purpose |
|-------|----|---------|
| Block | 0.0.10291833 | Tribunal batch records |
| Receipt | 0.0.10291834 | Deed issuance confirmations |
| Event | 0.0.10291836 | Judge registrations (seq 715-721) |
| POE | 0.0.10291838 | Merkle root anchors — FINALITY |

Operator key at `/home/swarm/Desktop/hedera-swarmfoundry/.env`.

## Finality Pipeline (5 layers)

1. PostgreSQL (hot queries — mutable)
2. MinIO `swarmdeed-finality` bucket on NAS (versioned archive)
3. IPFS (public, CID-addressable)
4. Hedera HCS (consensus timestamp — immutable)
5. swarmdeed.eth (permanent ENS URL)

All 5 layers must be populated before deeds are considered final. The Swarm Inspector validates this.

## What "Done" Means

- Code written and matches spec
- File read back / output verified
- Open items filed in OPEN_ITEMS.md
- New env vars documented
- Inspector passes on any deed-related changes
