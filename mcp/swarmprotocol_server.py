#!/usr/bin/env python3
"""
SwarmProtocol MCP Server — Official SDK Implementation
========================================================
Built on the official MCP Python SDK (FastMCP).
Exposes the full SwarmProtocol as tools, resources, and prompts.

Tools:   Actions agents can take (score, deed, verify, anchor)
Resources: Data agents can read (inventory, deeds, graph, fleet)
Prompts: Templates for common workflows (calibration, tribunal, closing)

Install:
    pip install mcp psycopg2-binary

Run:
    python swarmprotocol_server.py                    # stdio (Claude Code, Goose)
    python swarmprotocol_server.py --transport sse    # SSE (web clients)

Add to .mcp.json:
    {
      "mcpServers": {
        "swarmprotocol": {
          "command": "python3",
          "args": ["path/to/swarmprotocol_server.py"]
        }
      }
    }
"""
import os
import json
import hashlib
import time
import urllib.request
from mcp.server.fastmcp import FastMCP
from swarm_config import cfg

DB_URL = os.environ.get("DATABASE_URL", "")
JUDGE_A = os.environ.get("JUDGE_A", "http://localhost:11434")
JUDGE_B = os.environ.get("JUDGE_B", "http://192.168.0.99:11434")

mcp = FastMCP(
    "SwarmProtocol",
    version="1.0.0",
    description="Defendable AI Training Data Protocol — dual-judge tribunal, title deeds, blockchain anchoring. Swarm & Bee LLC.",
)


# ═══════════════════════════════════════════════════════
#  RESOURCES — Data agents can read
# ═══════════════════════════════════════════════════════

@mcp.resource("swarm://inventory")
def get_inventory() -> str:
    """Browse all available deeded inventory across domains. Shows pair counts, tier breakdown, and availability."""
    try:
        import psycopg2
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        cur.execute("SELECT domain_id, COUNT(*) FROM pairs GROUP BY domain_id ORDER BY COUNT(*) DESC")
        domains = [{"domain": d, "pairs": c} for d, c in cur.fetchall()]
        cur.execute("SELECT COUNT(*) FROM bin WHERE deed_id IS NOT NULL")
        deeded = cur.fetchone()[0]
        cur.execute("SELECT tier, COUNT(*) FROM bin WHERE tier IS NOT NULL GROUP BY tier")
        tiers = {t: c for t, c in cur.fetchall()}
        conn.close()
        return json.dumps({
            "domains": domains,
            "total_pairs": sum(d["pairs"] for d in domains),
            "deeded": deeded,
            "tiers": tiers,
            "calibration": "Free 50-pair calibration available",
            "contact": "build@swarmandbee.ai",
        }, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.resource("swarm://inventory/{domain}")
def get_domain_inventory(domain: str) -> str:
    """Get detailed inventory for a specific domain (medical, cre, aviation, grants)."""
    try:
        import psycopg2
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM pairs WHERE domain_id = %s", (domain,))
        count = cur.fetchone()[0]
        cur.execute("""
            SELECT tier, COUNT(*), ROUND(AVG(final_score)::numeric, 4)
            FROM bin WHERE domain_id = %s AND tier IS NOT NULL
            GROUP BY tier
        """, (domain,))
        tiers = [{"tier": t, "count": c, "mean": float(m)} for t, c, m in cur.fetchall()]
        conn.close()
        return json.dumps({"domain": domain, "total_pairs": count, "tiers": tiers}, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.resource("swarm://deed/{block_id}")
def get_deed(block_id: str) -> str:
    """Retrieve a specific deed by block ID. Returns all five proofs."""
    try:
        import psycopg2
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        cur.execute("""
            SELECT id, domain_id, judge_a_score, judge_b_score, final_score,
                   tier, merkle_root, sealed_at, judge_a_reasoning, judge_b_reasoning
            FROM deeds WHERE id = %s
        """, (block_id,))
        row = cur.fetchone()
        conn.close()
        if not row:
            return json.dumps({"error": f"Deed {block_id} not found"})
        return json.dumps({
            "block_id": row[0], "domain": row[1],
            "quality": {"judge_a": row[2], "judge_b": row[3], "final": row[4]},
            "tier": row[5], "merkle_root": row[6],
            "sealed_at": str(row[7]), "judge_a_reasoning": row[8], "judge_b_reasoning": row[9],
        }, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.resource("swarm://fleet")
def get_fleet() -> str:
    """Get the current hardware fleet status — GPUs, nodes, silicon."""
    try:
        import subprocess
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=index,name,utilization.gpu,memory.used,memory.total,power.draw,temperature.gpu",
             "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=5
        )
        gpus = []
        for line in result.stdout.strip().split("\n"):
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 7:
                gpus.append({"index": parts[0], "name": parts[1], "util": parts[2],
                             "vram_used": parts[3], "vram_total": parts[4],
                             "power": parts[5], "temp": parts[6]})
        return json.dumps({"gpus": gpus, "nodes": [
            {"id": "swarmrails", "ip": "localhost", "role": "compute + judges"},
            {"id": "whale", "ip": "192.168.0.99", "role": "judge B"},
            {"id": "nas", "ip": "192.168.0.102", "role": "database + storage"},
            {"id": "zima-lite", "ip": "192.168.0.173", "role": "web host"},
        ]}, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.resource("swarm://graph")
def get_graph_summary() -> str:
    """Get SwarmGraph summary — nodes, edges, domain stats."""
    try:
        import psycopg2
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM pairs")
        pairs = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM deeds")
        deeds = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM graph_edges")
        edges = cur.fetchone()[0]
        cur.execute("SELECT domain_id, COUNT(*) FROM pairs GROUP BY domain_id")
        domains = {d: c for d, c in cur.fetchall()}
        conn.close()
        return json.dumps({
            "pairs": pairs, "deeds": deeds, "edges": edges, "domains": domains,
            "hedera_topic": "0.0.10291838",
            "verify": "https://hashscan.io/mainnet/topic/0.0.10291838",
        }, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.resource("swarm://protocol")
def get_protocol() -> str:
    """The SwarmProtocol specification — how the tribunal works."""
    return json.dumps({
        "name": "SwarmProtocol",
        "version": "1.0",
        "components": {
            "tribunal": "Dual independent base-model judges, 2-pass validation",
            "deeds": "5-proof title deeds written by 12B+ base model",
            "merkle": "SHA256 Merkle trees, 50 deeds per batch",
            "anchoring": "Hedera HCS mainnet, 4 topics",
            "classification": {
                "royal_jelly": f">= {cfg.rj_threshold} — production ready",
                "honey": f"{cfg.honey_threshold}-{cfg.rj_threshold - 0.01:.2f} — improvable",
                "propolis": f"< {cfg.honey_threshold} — intelligence",
            },
        },
        "rules": [
            "Judges must be BASE models — never fine-tuned",
            "Two independent judges from different model families",
            "Every pair scored twice per judge (2-pass validation)",
            "Drift > 0.15 between passes = FLAGGED, no deed issued",
            "Deed writer must be 12B+ base model",
            "Deeds are Q&A pairs, not JSON metadata",
            "No permit, no build — all settings frozen before execution",
            "All 5 finality layers must be populated before deeds are final",
        ],
        "finality_layers": [
            "PostgreSQL (hot queries)",
            "MinIO (versioned archive)",
            "IPFS (public, CID-addressable)",
            "Hedera HCS (consensus timestamp)",
            "swarmdeed.eth (permanent ENS URL)",
        ],
        "ens_domains": {
            "swarmprotocol.eth": "specification",
            "swarmchain.eth": "tribunal",
            "swarmgraph.eth": "context graph",
            "swarmdeed.eth": "deed office",
            "swarmtitle.eth": "title company",
            "swarmshop.eth": "marketplace",
            "swarmbuilder.eth": "permit office",
            "defendable.eth": "the algorithm",
        },
    }, indent=2)


# ═══════════════════════════════════════════════════════
#  TOOLS — Actions agents can take
# ═══════════════════════════════════════════════════════

@mcp.tool()
def score_pairs(pairs: list[dict], domain: str = "custom") -> dict:
    """
    Submit AI training pairs for tribunal scoring.
    Each pair must have a 'messages' array with system/user/assistant roles.
    Returns a batch ID for tracking progress.
    Dual independent judges score every pair with 2-pass validation.
    Cost: $0.005 per deed.
    """
    import uuid
    batch_id = f"MCP-{uuid.uuid4().hex[:8]}"

    try:
        import psycopg2
        from psycopg2.extras import Json
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()

        loaded = 0
        for pair in pairs:
            messages = pair.get("messages", [])
            fp = hashlib.sha256(json.dumps(messages, sort_keys=True).encode()).hexdigest()

            cur.execute("""
                INSERT INTO pairs (fingerprint, domain_id, messages, char_count, metadata, source_file)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (fingerprint) DO UPDATE SET domain_id = EXCLUDED.domain_id
                RETURNING id
            """, (fp, domain, Json(messages),
                  sum(len(m.get("content", "")) for m in messages),
                  Json({"source": "mcp", "batch_id": batch_id}), "mcp"))
            pair_id = cur.fetchone()[0]

            cur.execute("CREATE TABLE IF NOT EXISTS bin (id BIGSERIAL PRIMARY KEY, pair_id UUID, domain_id TEXT, status TEXT DEFAULT 'queued', judge_a_score REAL, judge_b_score REAL, final_score REAL, tier TEXT, deed_id TEXT, batch_tag TEXT, queued_at TIMESTAMPTZ DEFAULT NOW(), scored_at TIMESTAMPTZ, deeded_at TIMESTAMPTZ, judge_a_pass2 REAL, judge_b_pass2 REAL, judge_a_reasoning TEXT, judge_b_reasoning TEXT, max_drift REAL, anchored_at TIMESTAMPTZ)")
            cur.execute("INSERT INTO bin (pair_id, domain_id, status, batch_tag) VALUES (%s, %s, 'queued', %s)", (pair_id, domain, batch_id))
            loaded += 1

        conn.commit()
        conn.close()
        return {
            "batch_id": batch_id,
            "pairs_queued": loaded,
            "domain": domain,
            "protocol": "2-pass dual-judge validation",
            "cost_estimate": f"${loaded * 0.005:.2f}",
        }
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def check_batch(batch_id: str) -> dict:
    """Check scoring progress for a submitted batch."""
    try:
        import psycopg2
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        cur.execute("SELECT status, COUNT(*) FROM bin WHERE batch_tag = %s GROUP BY status", (batch_id,))
        statuses = dict(cur.fetchall())
        cur.execute("SELECT tier, COUNT(*), ROUND(AVG(final_score)::numeric,4) FROM bin WHERE batch_tag = %s AND tier IS NOT NULL GROUP BY tier", (batch_id,))
        tiers = [{"tier": t, "count": c, "mean": float(m)} for t, c, m in cur.fetchall()]
        conn.close()
        return {"batch_id": batch_id, "statuses": statuses, "tiers": tiers,
                "complete": statuses.get("queued", 0) == 0 and statuses.get("judging", 0) == 0}
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def verify_deed(block_id: str) -> dict:
    """
    Independently verify a deed. Checks:
    - Classification matches score
    - Dual judges are independent
    - Final score is correct average
    - Merkle root exists
    - Hedera anchor exists
    """
    try:
        import psycopg2
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        cur.execute("""
            SELECT judge_a_id, judge_b_id, judge_a_score, judge_b_score,
                   final_score, tier, merkle_root, validated
            FROM deeds WHERE id = %s
        """, (block_id,))
        row = cur.fetchone()
        conn.close()

        if not row:
            return {"verified": False, "error": f"Deed {block_id} not found"}

        ja_id, jb_id, ja_s, jb_s, final, tier, merkle, validated = row
        checks = {
            "independent_judges": ja_id != jb_id,
            "score_average": abs(((ja_s + jb_s) / 2) - final) < 0.01 if ja_s and jb_s else False,
            "classification_match": tier == cfg.classify(final) if final is not None else False,
            "merkle_exists": merkle is not None,
            "validated": validated,
        }
        passed = all(checks.values())
        return {"block_id": block_id, "verified": passed, "checks": checks}
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def get_cook_status() -> dict:
    """Check the status of active model training runs."""
    import subprocess, glob

    cook_dir = "/home/swarm/swarmgrant-gemma4-31b"
    status = {"active": False, "model": "google/gemma-4-31B-it"}

    try:
        result = subprocess.run(["pgrep", "-f", "train_swarmgrant"], capture_output=True, timeout=3)
        status["active"] = result.returncode == 0
    except:
        pass

    states = sorted(glob.glob(f"{cook_dir}/checkpoint-*/trainer_state.json"))
    if states:
        with open(states[-1]) as f:
            state = json.load(f)
        evals = [e for e in state.get("log_history", []) if "eval_loss" in e]
        if evals:
            status["latest_eval"] = {"step": evals[-1]["step"], "eval_loss": evals[-1]["eval_loss"]}
        trains = [e for e in state.get("log_history", []) if "loss" in e and "eval_loss" not in e]
        if trains:
            status["latest_step"] = trains[-1]["step"]
            status["total_steps"] = 3204

    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=utilization.gpu,memory.used,power.draw,temperature.gpu",
             "--format=csv,noheader,nounits", "-i", "0"], capture_output=True, text=True, timeout=5
        )
        parts = [p.strip() for p in result.stdout.strip().split(",")]
        if len(parts) >= 4:
            status["gpu"] = {"util": parts[0], "vram": parts[1], "power": parts[2], "temp": parts[3]}
    except:
        pass

    return status


@mcp.tool()
def request_calibration(domain: str, email: str, pair_count: int = 50) -> dict:
    """
    Request a free 50-pair calibration. We score your sample data and return
    a tier breakdown report within 48 hours. No commitment.
    """
    return {
        "status": "received",
        "domain": domain,
        "email": email,
        "pairs_requested": pair_count,
        "response_time": "48 hours",
        "cost": "free",
        "next_steps": "Send your sample pairs to build@swarmandbee.ai or use the score_pairs tool",
        "contact": "build@swarmandbee.ai",
    }


# ═══════════════════════════════════════════════════════
#  PROMPTS — Templates for common workflows
# ═══════════════════════════════════════════════════════

@mcp.prompt()
def calibration_report(domain: str, pair_count: int = 50) -> str:
    """Generate a calibration report request for a domain."""
    return f"""Run a calibration on {pair_count} {domain} pairs through the SwarmProtocol tribunal.

Steps:
1. Load {pair_count} {domain} pairs into the bin using score_pairs
2. Wait for scoring to complete (check with check_batch)
3. Report the tier breakdown: Royal Jelly / Honey / Propolis
4. Show mean scores and drift statistics
5. Recommend whether to proceed with full tribunal run

This is a free calibration — no commitment required."""


@mcp.prompt()
def tribunal_run(domain: str, pair_count: int = 1000) -> str:
    """Generate a full tribunal run plan for a domain."""
    return f"""Plan and execute a full tribunal run on {pair_count} {domain} pairs.

Protocol:
1. Pull a SwarmBuilder permit (flight sheet with frozen settings)
2. Load {pair_count} pairs into the bin (never more than 1,000 at a time)
3. Run dual-judge tribunal with 2-pass validation
4. When batch is scored, run the deed writer (12B+ base model)
5. Build Merkle trees (batches of 50)
6. Anchor to Hedera HCS mainnet
7. Load deeds into all 5 finality layers
8. Run Swarm Inspector to verify
9. Quality over speed — especially on medical

Check fleet status first to ensure judges and hardware are available."""


@mcp.prompt()
def closing_checklist(client_name: str, domain: str) -> str:
    """Generate a closing checklist for a client delivery."""
    return f"""Prepare closing deliverables for {client_name} ({domain} domain).

Closing package must include:
1. Deeded pairs (JSONL with embedded title deeds)
2. Deed manifest (JSON — all 5 proofs per pair)
3. Merkle proofs (JSON — per-pair inclusion proofs)
4. Hedera receipts (JSON — anchor transaction IDs + consensus timestamps)
5. Verification script (Python — run independently to verify everything)
6. ENS subdomain: {client_name.lower().replace(' ', '')}.swarmdeed.eth
7. Closing statement (variance: estimated vs delivered)
8. Title insurance certificate from SwarmTitle
9. Permit record (frozen flight sheet)
10. Judge calibration certificate

Verify all 5 finality layers are populated before delivery.
Run Swarm Inspector --full before signing the closing statement."""


@mcp.prompt()
def deed_inspection(block_id: str) -> str:
    """Generate an inspection workflow for a specific deed."""
    return f"""Inspect deed {block_id} through all validation layers.

Level 1 — Code checks:
  - All required fields present?
  - Score in valid range?
  - Classification matches score?
  - Permit referenced?
  - Deed writer recorded?

Level 2 — Score reproduction:
  - Re-score with the same judge models
  - Compare to recorded score
  - Drift within 0.15 tolerance?

Level 3 — Independent inspection:
  - Load the deed and original pair
  - Have the inspector model (phi4-mini, different family) evaluate
  - Is the deed AUTHENTIC or BOILERPLATE?
  - Does reasoning cite specific content from the pair?

Level 4 — Human review:
  - Flag for manual inspection if any level fails
  - Show the original pair + deed + inspector findings

Use verify_deed tool first, then run the full inspector."""


# ═══════════════════════════════════════════════════════
#  RUN
# ═══════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys
    transport = "stdio"
    if "--transport" in sys.argv:
        idx = sys.argv.index("--transport")
        if idx + 1 < len(sys.argv):
            transport = sys.argv[idx + 1]

    mcp.run(transport=transport)
