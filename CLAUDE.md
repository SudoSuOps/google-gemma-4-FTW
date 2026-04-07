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
- **Whale**: RTX 3090 24GB at 192.168.0.99 — idle — ollama disabled
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

<!-- gitnexus:start -->
# GitNexus — Code Intelligence

This project is indexed by GitNexus as **google-gemma-4-FTW** (832 symbols, 1621 relationships, 67 execution flows). Use the GitNexus MCP tools to understand code, assess impact, and navigate safely.

> If any GitNexus tool warns the index is stale, run `npx gitnexus analyze` in terminal first.

## Always Do

- **MUST run impact analysis before editing any symbol.** Before modifying a function, class, or method, run `gitnexus_impact({target: "symbolName", direction: "upstream"})` and report the blast radius (direct callers, affected processes, risk level) to the user.
- **MUST run `gitnexus_detect_changes()` before committing** to verify your changes only affect expected symbols and execution flows.
- **MUST warn the user** if impact analysis returns HIGH or CRITICAL risk before proceeding with edits.
- When exploring unfamiliar code, use `gitnexus_query({query: "concept"})` to find execution flows instead of grepping. It returns process-grouped results ranked by relevance.
- When you need full context on a specific symbol — callers, callees, which execution flows it participates in — use `gitnexus_context({name: "symbolName"})`.

## When Debugging

1. `gitnexus_query({query: "<error or symptom>"})` — find execution flows related to the issue
2. `gitnexus_context({name: "<suspect function>"})` — see all callers, callees, and process participation
3. `READ gitnexus://repo/google-gemma-4-FTW/process/{processName}` — trace the full execution flow step by step
4. For regressions: `gitnexus_detect_changes({scope: "compare", base_ref: "main"})` — see what your branch changed

## When Refactoring

- **Renaming**: MUST use `gitnexus_rename({symbol_name: "old", new_name: "new", dry_run: true})` first. Review the preview — graph edits are safe, text_search edits need manual review. Then run with `dry_run: false`.
- **Extracting/Splitting**: MUST run `gitnexus_context({name: "target"})` to see all incoming/outgoing refs, then `gitnexus_impact({target: "target", direction: "upstream"})` to find all external callers before moving code.
- After any refactor: run `gitnexus_detect_changes({scope: "all"})` to verify only expected files changed.

## Never Do

- NEVER edit a function, class, or method without first running `gitnexus_impact` on it.
- NEVER ignore HIGH or CRITICAL risk warnings from impact analysis.
- NEVER rename symbols with find-and-replace — use `gitnexus_rename` which understands the call graph.
- NEVER commit changes without running `gitnexus_detect_changes()` to check affected scope.

## Tools Quick Reference

| Tool | When to use | Command |
|------|-------------|---------|
| `query` | Find code by concept | `gitnexus_query({query: "auth validation"})` |
| `context` | 360-degree view of one symbol | `gitnexus_context({name: "validateUser"})` |
| `impact` | Blast radius before editing | `gitnexus_impact({target: "X", direction: "upstream"})` |
| `detect_changes` | Pre-commit scope check | `gitnexus_detect_changes({scope: "staged"})` |
| `rename` | Safe multi-file rename | `gitnexus_rename({symbol_name: "old", new_name: "new", dry_run: true})` |
| `cypher` | Custom graph queries | `gitnexus_cypher({query: "MATCH ..."})` |

## Impact Risk Levels

| Depth | Meaning | Action |
|-------|---------|--------|
| d=1 | WILL BREAK — direct callers/importers | MUST update these |
| d=2 | LIKELY AFFECTED — indirect deps | Should test |
| d=3 | MAY NEED TESTING — transitive | Test if critical path |

## Resources

| Resource | Use for |
|----------|---------|
| `gitnexus://repo/google-gemma-4-FTW/context` | Codebase overview, check index freshness |
| `gitnexus://repo/google-gemma-4-FTW/clusters` | All functional areas |
| `gitnexus://repo/google-gemma-4-FTW/processes` | All execution flows |
| `gitnexus://repo/google-gemma-4-FTW/process/{name}` | Step-by-step execution trace |

## Self-Check Before Finishing

Before completing any code modification task, verify:
1. `gitnexus_impact` was run for all modified symbols
2. No HIGH/CRITICAL risk warnings were ignored
3. `gitnexus_detect_changes()` confirms changes match expected scope
4. All d=1 (WILL BREAK) dependents were updated

## Keeping the Index Fresh

After committing code changes, the GitNexus index becomes stale. Re-run analyze to update it:

```bash
npx gitnexus analyze
```

If the index previously included embeddings, preserve them by adding `--embeddings`:

```bash
npx gitnexus analyze --embeddings
```

To check whether embeddings exist, inspect `.gitnexus/meta.json` — the `stats.embeddings` field shows the count (0 means no embeddings). **Running analyze without `--embeddings` will delete any previously generated embeddings.**

> Claude Code users: A PostToolUse hook handles this automatically after `git commit` and `git merge`.

## CLI

| Task | Read this skill file |
|------|---------------------|
| Understand architecture / "How does X work?" | `.claude/skills/gitnexus/gitnexus-exploring/SKILL.md` |
| Blast radius / "What breaks if I change X?" | `.claude/skills/gitnexus/gitnexus-impact-analysis/SKILL.md` |
| Trace bugs / "Why is X failing?" | `.claude/skills/gitnexus/gitnexus-debugging/SKILL.md` |
| Rename / extract / split / refactor | `.claude/skills/gitnexus/gitnexus-refactoring/SKILL.md` |
| Tools, resources, schema reference | `.claude/skills/gitnexus/gitnexus-guide/SKILL.md` |
| Index, status, clean, wiki CLI commands | `.claude/skills/gitnexus/gitnexus-cli/SKILL.md` |

<!-- gitnexus:end -->
