# SwarmTribunal MCP Server

**Dual-judge AI training data quality scoring as a tool for any AI agent.**

## Install

Add to your `.mcp.json` (Claude Code, Goose, Cursor):

```json
{
  "mcpServers": {
    "swarmtribunal": {
      "command": "python3",
      "args": ["/path/to/swarmtribunal-mcp.py"]
    }
  }
}
```

## Tools

| Tool | What it does |
|------|-------------|
| `score_pairs` | Submit pairs for dual-judge tribunal scoring |
| `check_status` | Check scoring progress for a batch |
| `get_deed` | Retrieve a deed by block ID |
| `verify_deed` | Run independent verification |
| `get_inventory` | Browse available deeded inventory |

## Example

```
You: Score these 10 training pairs for quality

Agent → calls score_pairs({pairs: [...], domain: "medical"})
     ← returns {batch_id: "MCP-a1b2c3d4", pairs_queued: 10, cost: "$0.05"}

You: Check the status

Agent → calls check_status({batch_id: "MCP-a1b2c3d4"})
     ← returns {scored: 10, royal_jelly: 9, honey: 1}
```

## What Happens

1. Your pairs go into the SwarmChain bin
2. Two independent base judges score every pair (2-pass validation)
3. Pairs that pass get a title deed with 5 proofs
4. Merkle root anchored to Hedera HCS (mainnet)
5. You get back deeded pairs with full provenance

## Judges

| Judge | Model | Hardware | Modified? |
|-------|-------|----------|-----------|
| A | gemma3:12b | RTX PRO 6000 Blackwell | No — base |
| B | qwen2.5:7b | RTX 3090 Ampere | No — base |

## Pricing

$0.005 per deed. Free 50-pair calibration.

## Verify

- Hedera: [hashscan.io/mainnet/topic/0.0.10291838](https://hashscan.io/mainnet/topic/0.0.10291838)
- Graph: [swarmgraph.eth.limo](https://swarmgraph.eth.limo)
- Shop: [swarmshop.eth.limo](https://swarmshop.eth.limo)
- Deeds: [swarmdeed.eth.limo](https://swarmdeed.eth.limo)

**Swarm & Bee LLC** — build@swarmandbee.ai
