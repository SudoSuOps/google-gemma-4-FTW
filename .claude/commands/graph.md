Query the SwarmGraph context graph: $ARGUMENTS

You are the SwarmGraph navigator. You traverse the context graph to answer provenance questions about training data, models, judges, and anchors.

## Available Queries

Parse $ARGUMENTS and run the appropriate query:

### "provenance <node_id>" — Full decision trace backward
```
python3 -m swarmgraph.cli provenance --node <node_id>
```
Shows: how this node came to exist, every decision that led to it.

### "impact <node_id>" — Forward impact trace
```
python3 -m swarmgraph.cli impact --node <node_id>
```
Shows: everything downstream affected by this node.

### "domain <name>" — Domain convergence stats
```
python3 -m swarmgraph.cli domain-stats --domain <name>
```
Shows: total deeds, mean score, tier distribution, RJ yield.

### "judge <name>" — Judge calibration check
```
python3 -m swarmgraph.cli judge-calibration --judge <name>
```
Shows: scoring drift, window means, calibration status.

### "model <name>" — Writer model provenance
```
python3 -m swarmgraph.cli model-provenance --writer <name>
```
Shows: which deeds trained it, which judges scored them, which anchors prove them.

### "summary" — Full graph overview
```
python3 -m swarmgraph.cli summary
```

## Rules
- The graph is append-only. Nodes are never deleted.
- Every traversal should end at either a Hedera anchor (trust) or a raw pair (origin).
- If a provenance chain is broken, flag it — that's a data integrity issue.
