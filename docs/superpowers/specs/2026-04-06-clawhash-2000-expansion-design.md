# ClawHash 2,000 Pair Expansion — Design Spec

**Date**: 2026-04-06
**Status**: Approved
**Target**: 2,000 adversarial pairs from 70 templates, all-local generation

## Problem

89 ClawHash pairs exist (87 RJ, 100% Class A). Need 1,000+ RJ to unlock on shop. Target: 2,000 pairs from expanded template set to sustain variety.

## Approach

Expand templates from 33 → 70 using CVE sources, broken-weights intelligence, and X signal data. Split red/blue team models for attack diversity. Run all-local on the 256GB VRAM rig.

## Models (All Local)

| Role | Model | GPU | Why |
|------|-------|-----|-----|
| Red team (attacks) | gemma4:31b | GPU 0 (96GB) | Different family = diverse attacks |
| Blue team (defenses) | qwen3.5:27b | GPU 0/1 (96GB) | Target model for training |

## Template Expansion

### Existing files — additions (24 new templates)

| File | Current | Adding | New Total | New Patterns |
|------|---------|--------|-----------|--------------|
| injection.json | 8 | +4 | 12 | CoT injection, markdown exfil, few-shot poisoning, recursive injection |
| toolpoison.json | 6 | +5 | 11 | Tool shadowing, rug pulls, cross-origin confusion, hidden tool instructions, delayed activation |
| rce.json | 5 | +4 | 9 | Container escape via agent, env var exfil chaining, command chaining via shell ops, deserialization |
| supply.json | 5 | +4 | 9 | Typosquatting v2, dependency confusion v2, version rollback, star-count fraud |
| sandbox.json | 5 | +4 | 9 | Timing side-channel, procfs escape, tmpdir race, capability abuse |
| audit.json | 4 | +3 | 7 | Log injection (false entries), timestamp manipulation, alert fatigue flooding |

### New sub-algorithm files (13 new templates)

| File | Templates | Attack Pattern | Source |
|------|-----------|----------------|--------|
| drift.json | 5 | Model drifts from structured to narrated tool calls mid-session; attacker exploits to get dangerous ops narrated | Broken Weights Pattern 1, X signal #4 (hallucinated success) |
| corruptturn.json | 4 | Unclosed think tags, repeated tokens, format switches poison subsequent turns; attacker injects trigger content | Broken Weights Pattern 3, Qwen/Ollama bugs |
| fakeexec.json | 4 | Model claims tool execution but narrates instead, or hallucinates results; attacker leverages to bypass verification | X signal #4/#6, HN "silent death" pattern |

### Totals

- **70 templates** across 9 sub-algorithm files
- **2,000 pairs** at ~28 variants per template (within Claude's/Gemma's creativity window)
- **Expected RJ%**: 90%+ based on calibration
- **Expected yield**: ~1,800 RJ

## Generator Code Changes

1. Add `OLLAMA_RED_MODEL` env var (default: `gemma4:31b`)
2. Update `call_ollama_redteam()` to use `OLLAMA_RED_MODEL`
3. Add 3 entries to `SUB_ALGORITHM_MAP`: drift, corruptturn, fakeexec

## Pair Distribution (2,000 pairs)

| Sub-Algorithm | Templates | Pairs | % |
|--------------|-----------|-------|---|
| Injection | 12 | 400 | 20% |
| ToolPoison | 11 | 340 | 17% |
| RCE | 9 | 240 | 12% |
| Supply | 9 | 240 | 12% |
| Sandbox | 9 | 240 | 12% |
| Audit | 7 | 160 | 8% |
| Drift | 5 | 140 | 7% |
| CorruptTurn | 4 | 120 | 6% |
| FakeExec | 4 | 120 | 6% |

## Run Command

```bash
OLLAMA_RED_MODEL="gemma4:31b" OLLAMA_MODEL="qwen3.5:27b" \
  python3 scripts/generate_clawhash.py --count 2000 \
  --output domains/clawhash/raw/clawhash_2000.jsonl
```

## Success Criteria

1. 2,000 pairs generated across 9 sub-algorithms
2. All pairs load into tribunal bin
3. RJ% >= 85% after tribunal weighing
4. ClawHash unlocks on shop (1,000+ RJ)
5. Attack variety sustained (no repetitive clusters)

## What Doesn't Change

- Scoring prompt (existing 5 dimensions)
- Tribunal pipeline (existing bin → weigh → deed)
- Personas (3 agent types)
- Output JSONL format

---

*Intelligence: ~/Swarm-Wiki/19-research/clawhash-intelligence.md*
*Broken weights: ~/Swarm-Wiki/19-research/broken-weights-intelligence.md*
*X signal: ~/Swarm-Wiki/13-competitive/x-signal-openclaw-april-2026.md*
*Prior spec: docs/superpowers/specs/2026-04-06-clawhash-pair-generator-design.md*
