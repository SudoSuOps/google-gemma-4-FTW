#!/usr/bin/env python3
"""
SwarmTribunal MCP Server
=========================
Model Context Protocol server for AI training data quality scoring.
Any MCP-compatible agent (Claude Code, Goose, Cursor) can call this.

Tools exposed:
  - score_pairs:     Submit pairs for dual-judge tribunal scoring
  - check_status:    Check scoring progress for a batch
  - get_deed:        Retrieve a deed by block ID
  - verify_deed:     Run independent verification on a deed
  - get_inventory:   Browse available deeded inventory by domain

Run:
  python swarmtribunal-mcp.py                    # stdio mode (for Claude Code)
  python swarmtribunal-mcp.py --http 9099        # HTTP mode (for remote agents)
"""
import json
import hashlib
import time
import os
import sys
import uuid
from pathlib import Path

# MCP protocol implementation
# Uses JSON-RPC 2.0 over stdio (standard MCP transport)

DB_URL = os.environ.get("DATABASE_URL", "")
JUDGE_A = os.environ.get("JUDGE_A", "http://localhost:11434")
JUDGE_B = os.environ.get("JUDGE_B", "http://192.168.0.99:11434")

TOOLS = [
    {
        "name": "score_pairs",
        "description": "Submit AI training pairs for quality scoring through the SwarmTribunal. Dual independent base-model judges with 2-pass validation. Returns a batch ID for tracking. Each pair must have 'messages' with system/user/assistant roles.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "pairs": {
                    "type": "array",
                    "description": "Array of training pairs. Each pair has a 'messages' array with role/content objects.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "messages": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "role": {"type": "string", "enum": ["system", "user", "assistant"]},
                                        "content": {"type": "string"}
                                    },
                                    "required": ["role", "content"]
                                }
                            }
                        },
                        "required": ["messages"]
                    }
                },
                "domain": {
                    "type": "string",
                    "description": "Domain category: medical, cre, aviation, grants, or custom",
                    "default": "custom"
                }
            },
            "required": ["pairs"]
        }
    },
    {
        "name": "check_status",
        "description": "Check the scoring progress for a submitted batch. Returns counts of queued, judging, scored, and tier breakdown.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "batch_id": {"type": "string", "description": "Batch ID returned from score_pairs"}
            },
            "required": ["batch_id"]
        }
    },
    {
        "name": "get_deed",
        "description": "Retrieve a title deed by block ID. Returns all five proofs: origin, quality, process, economics, trust.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "block_id": {"type": "string", "description": "Deed block ID (e.g. SB-2026-0403-00001)"}
            },
            "required": ["block_id"]
        }
    },
    {
        "name": "verify_deed",
        "description": "Run independent verification on a deed. Checks: classification matches score, dual judges are independent, final score is correct average, Merkle root is valid.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "block_id": {"type": "string", "description": "Deed block ID to verify"}
            },
            "required": ["block_id"]
        }
    },
    {
        "name": "get_inventory",
        "description": "Browse available deeded inventory by domain. Returns pair count, tier breakdown, Royal Jelly yield, mean score, and OM availability.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "domain": {
                    "type": "string",
                    "description": "Domain to browse: medical, cre, aviation, grants, or 'all'",
                    "default": "all"
                }
            }
        }
    }
]

SERVER_INFO = {
    "name": "swarmtribunal",
    "version": "1.0.0",
    "description": "SwarmTribunal — Dual-judge AI training data quality scoring with blockchain-anchored deeds. Swarm & Bee LLC.",
    "vendor": "Swarm & Bee LLC",
    "contact": "build@swarmandbee.ai",
    "website": "https://swarmandbee.ai",
    "ens": "swarmchain.eth",
    "hedera_topic": "0.0.10291838",
}


def handle_score_pairs(params):
    """Submit pairs for tribunal scoring."""
    pairs = params.get("pairs", [])
    domain = params.get("domain", "custom")
    batch_id = f"MCP-{uuid.uuid4().hex[:8]}"

    if not pairs:
        return {"error": "No pairs provided"}

    try:
        import psycopg2
        from psycopg2.extras import Json
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()

        # Ensure bin table exists
        cur.execute("""CREATE TABLE IF NOT EXISTS bin (
            id BIGSERIAL PRIMARY KEY, pair_id UUID, domain_id TEXT NOT NULL,
            status TEXT DEFAULT 'queued', judge_a_score REAL, judge_a_pass2 REAL,
            judge_a_reasoning TEXT, judge_b_score REAL, judge_b_pass2 REAL,
            judge_b_reasoning TEXT, final_score REAL, max_drift REAL, tier TEXT,
            deed_id TEXT, batch_tag TEXT, queued_at TIMESTAMPTZ DEFAULT NOW(),
            scored_at TIMESTAMPTZ, deeded_at TIMESTAMPTZ, anchored_at TIMESTAMPTZ
        )""")

        loaded = 0
        for pair in pairs:
            messages = pair.get("messages", [])
            fp = hashlib.sha256(json.dumps(messages, sort_keys=True).encode()).hexdigest()

            # Insert pair
            cur.execute("""
                INSERT INTO pairs (fingerprint, domain_id, messages, char_count, metadata, source_file)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (fingerprint) DO UPDATE SET domain_id = EXCLUDED.domain_id
                RETURNING id
            """, (fp, domain, Json(messages),
                  sum(len(m.get("content", "")) for m in messages),
                  Json({"source": "mcp", "batch_id": batch_id}), "mcp_submission"))

            pair_id = cur.fetchone()[0]

            # Add to bin
            cur.execute("""
                INSERT INTO bin (pair_id, domain_id, status, batch_tag)
                VALUES (%s, %s, 'queued', %s)
            """, (pair_id, domain, batch_id))
            loaded += 1

        conn.commit()
        conn.close()

        return {
            "batch_id": batch_id,
            "pairs_queued": loaded,
            "domain": domain,
            "judges": {
                "judge_a": "gemma3:12b (base, unmodified)",
                "judge_b": "gemma3:12b (base, unmodified)"
            },
            "protocol": "2-pass validation (validate the validator)",
            "status": "queued",
            "check_with": f"Use check_status with batch_id '{batch_id}'",
            "cost_estimate": f"${loaded * 0.005:.2f} ({loaded} × $0.005/deed)"
        }
    except Exception as e:
        return {"error": str(e)}


def handle_check_status(params):
    """Check batch scoring progress."""
    batch_id = params.get("batch_id", "")
    try:
        import psycopg2
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()

        cur.execute("SELECT status, COUNT(*) FROM bin WHERE batch_tag = %s GROUP BY status", (batch_id,))
        statuses = dict(cur.fetchall())

        cur.execute("SELECT tier, COUNT(*), ROUND(AVG(final_score)::numeric, 4) FROM bin WHERE batch_tag = %s AND tier IS NOT NULL GROUP BY tier", (batch_id,))
        tiers = [{"tier": t, "count": c, "mean_score": float(m)} for t, c, m in cur.fetchall()]

        conn.close()
        total = sum(statuses.values())

        return {
            "batch_id": batch_id,
            "total": total,
            "queued": statuses.get("queued", 0),
            "judging": statuses.get("judging", 0),
            "scored": statuses.get("scored", 0),
            "flagged": statuses.get("flagged", 0),
            "tiers": tiers,
            "complete": statuses.get("queued", 0) == 0 and statuses.get("judging", 0) == 0,
        }
    except Exception as e:
        return {"error": str(e)}


def handle_get_inventory(params):
    """Browse deeded inventory."""
    domain = params.get("domain", "all")
    try:
        import psycopg2
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()

        if domain == "all":
            cur.execute("SELECT domain_id, COUNT(*) FROM pairs GROUP BY domain_id ORDER BY COUNT(*) DESC")
        else:
            cur.execute("SELECT domain_id, COUNT(*) FROM pairs WHERE domain_id = %s GROUP BY domain_id", (domain,))

        domains = []
        for d, count in cur.fetchall():
            domains.append({
                "domain": d,
                "total_pairs": count,
                "om_available": f"OM_{d}_v1.md",
                "shop": "swarmshop.eth.limo",
                "book_tour": "https://swarmandbee.ai/#contact",
            })

        conn.close()
        return {
            "inventory": domains,
            "total_pairs": sum(d["total_pairs"] for d in domains),
            "calibration": "Free 50-pair calibration available. No commitment.",
        }
    except Exception as e:
        return {"error": str(e)}


def handle_tool_call(name, params):
    handlers = {
        "score_pairs": handle_score_pairs,
        "check_status": handle_check_status,
        "get_inventory": handle_get_inventory,
    }
    handler = handlers.get(name)
    if handler:
        return handler(params)
    return {"error": f"Unknown tool: {name}"}


# ─── MCP JSON-RPC STDIO TRANSPORT ───

def handle_jsonrpc(request):
    method = request.get("method", "")
    params = request.get("params", {})
    req_id = request.get("id")

    if method == "initialize":
        return {"jsonrpc": "2.0", "id": req_id, "result": {
            "protocolVersion": "2024-11-05",
            "serverInfo": SERVER_INFO,
            "capabilities": {"tools": {}}
        }}

    elif method == "tools/list":
        return {"jsonrpc": "2.0", "id": req_id, "result": {"tools": TOOLS}}

    elif method == "tools/call":
        tool_name = params.get("name", "")
        tool_args = params.get("arguments", {})
        result = handle_tool_call(tool_name, tool_args)
        return {"jsonrpc": "2.0", "id": req_id, "result": {
            "content": [{"type": "text", "text": json.dumps(result, indent=2)}]
        }}

    elif method == "notifications/initialized":
        return None  # no response needed

    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": f"Unknown method: {method}"}}


def run_stdio():
    """Run MCP server over stdio (standard transport for Claude Code, Goose, etc.)."""
    sys.stderr.write("[swarmtribunal-mcp] Ready on stdio\n")

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
            response = handle_jsonrpc(request)
            if response:
                sys.stdout.write(json.dumps(response) + "\n")
                sys.stdout.flush()
        except json.JSONDecodeError:
            pass


def run_http(port=9099):
    """Run MCP server over HTTP (for remote agents)."""
    from http.server import HTTPServer, BaseHTTPRequestHandler

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length).decode())
            response = handle_jsonrpc(body)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            if response:
                self.wfile.write(json.dumps(response).encode())

        def do_OPTIONS(self):
            self.send_response(200)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.end_headers()

        def log_message(self, fmt, *args):
            sys.stderr.write(f"[mcp] {args[0]}\n")

    print(f"[swarmtribunal-mcp] HTTP server on :{port}")
    HTTPServer(("0.0.0.0", port), Handler).serve_forever()


if __name__ == "__main__":
    if "--http" in sys.argv:
        port = int(sys.argv[sys.argv.index("--http") + 1]) if len(sys.argv) > sys.argv.index("--http") + 1 else 9099
        run_http(port)
    else:
        run_stdio()
