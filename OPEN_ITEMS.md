# OPEN ITEMS

| ID | Description | Priority | Owner | Status |
|----|-------------|----------|-------|--------|
| OI-001 | Graph UI at swarmandbee.ai/graph/ needs live API wiring (ops/graph endpoint added, UI updated but not deployed to Zima) | P1 | Dev | OPEN |
| OI-002 | Deed writer (gemma3:12b) running — 395/5,022 complete. Finality pipeline pending completion | P0 | Dev | IN PROGRESS |
| OI-003 | PostgreSQL deeds table empty — load after deed writer completes all 5,022 | P0 | Dev | BLOCKED on OI-002 |
| OI-004 | Hedera re-anchor needed — previous anchors were from shortcut JSON deeds (not model-written). Must re-anchor after proper deeds complete | P0 | Dev | BLOCKED on OI-002 |
| OI-005 | Inspector (Swarm-Inspector) needs more original pair context in Level 3 prompt — truncating too aggressively for phi4 to verify specific references | P1 | Dev | OPEN |
| OI-006 | Ollama needs full upgrade to support Gemma 4 E2B as judge — currently on 0.15.2 server / 0.20.0 client mismatch | P2 | Dev | OPEN |
| OI-007 | swarmdeed.eth showing static demo deed — needs real deed data after finality pipeline completes | P1 | Dev | BLOCKED on OI-002 |
| OI-008 | swarmgraph.eth.limo IPFS content needs update after graph UI wired to live API | P1 | Dev | BLOCKED on OI-001 |
| OI-009 | MinIO object lock (write-once) not confirmed — using NFS fallback for deed archival | P2 | Dev | OPEN |
| OI-010 | Gemma 4 31B cook at step ~1,400/3,204 (44%) — ETA ~33 hours remaining | P0 | System | IN PROGRESS |
| OI-011 | Closing document templates (docs/closing/) have placeholder fields — need automation script to populate from real tribunal data | P2 | Dev | OPEN |
| OI-012 | Next med tribunal run needs DIFFERENT judges (protocol: model-agnostic, validate with different witnesses) | P1 | Swarm | PLANNED |
| OI-013 | Swarm-Inspector git repo needs deed_writer.py and updated prompts synced | P1 | Dev | OPEN |
