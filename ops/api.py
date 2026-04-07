#!/usr/bin/env python3
"""
SwarmOps API — Real-Time Infrastructure Data
=============================================
Serves live data for all ENS dashboards:
  /ops/status      — full system status
  /ops/gpus        — GPU utilization, VRAM, temp, power
  /ops/cook        — active cook status + loss trajectory
  /ops/fleet       — fleet node health
  /ops/db          — database stats (pairs, deeds, edges)
  /ops/domains     — domain breakdown
  /ops/graph       — SwarmGraph summary
  /ops/ens         — ENS domain status

Runs on swarmrails, proxied via Zima nginx.
CORS enabled for IPFS-hosted dashboards.

Usage:
    python3 api.py                      # Port 9090
    python3 api.py --port 9090
"""
import json
import subprocess
import time
import os
import glob
import argparse
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

DB_URL = os.environ.get("DATABASE_URL", "")

# ─── DATA COLLECTORS ───

def get_gpu_status():
    """Live GPU stats from nvidia-smi."""
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=index,name,utilization.gpu,memory.used,memory.total,power.draw,power.limit,temperature.gpu",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5
        )
        gpus = []
        for line in result.stdout.strip().split("\n"):
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 8:
                gpus.append({
                    "index": int(parts[0]),
                    "name": parts[1],
                    "utilization": int(parts[2]),
                    "memory_used_mb": int(parts[3]),
                    "memory_total_mb": int(parts[4]),
                    "power_draw_w": float(parts[5]),
                    "power_limit_w": float(parts[6]),
                    "temperature_c": int(parts[7]),
                })
        return gpus
    except Exception as e:
        return [{"error": str(e)}]


def get_cook_status():
    """Active training cook status."""
    cooks = []
    cook_dirs = [
        ("/home/swarm/swarmgrant-gemma4-31b", "swarmGrant-Gemma4-31B", "google/gemma-4-31B-it"),
    ]

    for cook_dir, name, base in cook_dirs:
        cook = {"name": name, "base": base, "dir": cook_dir, "active": False}

        # Check if process running
        try:
            result = subprocess.run(["pgrep", "-f", os.path.basename(cook_dir)], capture_output=True, timeout=3)
            cook["active"] = result.returncode == 0
        except:
            pass

        # Get latest step from log
        log_path = os.path.join(cook_dir, "train.log")
        if os.path.exists(log_path):
            try:
                result = subprocess.run(
                    ["tail", "-c", "2000", log_path],
                    capture_output=True, text=True, timeout=3
                )
                import re
                steps = re.findall(r"(\d+)/(\d+)", result.stdout.replace("\r", "\n"))
                if steps:
                    cook["step"] = int(steps[-1][0])
                    cook["total_steps"] = int(steps[-1][1])
                    cook["progress"] = round(cook["step"] / cook["total_steps"] * 100, 1)
            except:
                pass

        # Get loss from checkpoints
        states = sorted(glob.glob(os.path.join(cook_dir, "checkpoint-*/trainer_state.json")))
        if states:
            try:
                with open(states[-1]) as f:
                    state = json.load(f)
                logs = state.get("log_history", [])
                train_losses = [e for e in logs if "loss" in e and "eval_loss" not in e]
                eval_losses = [e for e in logs if "eval_loss" in e]

                if train_losses:
                    cook["train_loss"] = train_losses[-1]["loss"]
                    cook["epoch"] = train_losses[-1].get("epoch", 0)
                    cook["lr"] = train_losses[-1].get("learning_rate", 0)
                if eval_losses:
                    cook["eval_loss"] = eval_losses[-1]["eval_loss"]

                cook["loss_history"] = [
                    {"step": e.get("step", 0), "loss": e["loss"]}
                    for e in train_losses[-20:]
                ]
                cook["eval_history"] = [
                    {"step": e.get("step", 0), "eval_loss": e["eval_loss"]}
                    for e in eval_losses
                ]
            except:
                pass

        cooks.append(cook)

    return cooks


def get_fleet_status():
    """Fleet node health via ping."""
    nodes = [
        {"id": "swarmrails", "ip": "localhost", "hardware": "2x RTX PRO 6000 Blackwell + Xeon 72T", "role": "compute"},
        {"id": "whale", "ip": "192.168.0.99", "hardware": "RTX 3090 24GB + Ryzen 9", "role": "inference"},
        {"id": "sigedge", "ip": "192.168.0.79", "hardware": "Jetson Orin Nano 8GB", "role": "edge"},
        {"id": "zima-lite", "ip": "192.168.0.173", "hardware": "Celeron N3450 8GB", "role": "web"},
        {"id": "zima-edge-1", "ip": "192.168.0.230", "hardware": "N150 + T1000 (pending)", "role": "edge"},
        {"id": "nas", "ip": "192.168.0.102", "hardware": "Ryzen V1500B 8GB RAID1", "role": "storage"},
    ]

    for node in nodes:
        try:
            result = subprocess.run(
                ["ping", "-c", "1", "-W", "1", node["ip"]],
                capture_output=True, timeout=3
            )
            node["online"] = result.returncode == 0
        except:
            node["online"] = node["ip"] == "localhost"

    return nodes


def get_db_stats():
    """Database statistics from PostgreSQL."""
    try:
        import psycopg2
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()

        stats = {}
        for table in ["pairs", "deeds", "graph_edges", "audit_log", "tribunal_scores"]:
            cur.execute(f"SELECT COUNT(*) FROM {table}")
            stats[table] = cur.fetchone()[0]

        cur.execute("SELECT domain_id, COUNT(*) FROM pairs GROUP BY domain_id ORDER BY COUNT(*) DESC")
        stats["domains"] = {r[0]: r[1] for r in cur.fetchall()}

        cur.execute("SELECT COUNT(*) FROM deeds WHERE tier = 'royal_jelly'")
        stats["royal_jelly"] = cur.fetchone()[0]

        conn.close()
        stats["status"] = "online"
        stats["host"] = "192.168.0.102:5433"
        return stats
    except Exception as e:
        return {"status": "offline", "error": str(e)}


def get_storage():
    """Disk usage across all mounts."""
    try:
        result = subprocess.run(["df", "-h"], capture_output=True, text=True, timeout=5)
        mounts = []
        for line in result.stdout.strip().split("\n")[1:]:
            parts = line.split()
            if len(parts) >= 6 and any(m in parts[5] for m in ["/data", "/home", "/mnt/swarm"]):
                mounts.append({
                    "mount": parts[5],
                    "size": parts[1],
                    "used": parts[2],
                    "avail": parts[3],
                    "pct": parts[4],
                })
        return mounts
    except:
        return []


def get_live_graph():
    """Live graph data for the SwarmGraph UI."""
    try:
        import psycopg2
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()

        nodes = []
        edges = []

        # Domain nodes
        cur.execute("SELECT domain_id, COUNT(*) FROM pairs GROUP BY domain_id")
        for domain, count in cur.fetchall():
            nodes.append({"id": f"domain:{domain}", "type": "domain", "properties": {"name": domain, "pairs": count}})

        # Judge nodes
        cur.execute("SELECT id, model, label FROM judges")
        for jid, model, label in cur.fetchall():
            nodes.append({"id": f"judge:{jid}", "type": "judge", "properties": {"model": model, "label": label, "modified": False}})

        # Silicon nodes
        cur.execute("SELECT id, hardware, arch, power_watts, location FROM silicon")
        for sid, hw, arch, watts, loc in cur.fetchall():
            nodes.append({"id": f"silicon:{sid}", "type": "silicon", "properties": {"hardware": hw, "arch": arch, "power_watts": watts, "location": loc}})

        # Writer nodes
        cur.execute("SELECT id, model_name, status, eval_loss FROM writers")
        for wid, name, status, loss in cur.fetchall():
            nodes.append({"id": f"writer:{wid}", "type": "writer", "properties": {"model": name, "status": status, "eval_loss": float(loss) if loss else None}})

        # Deed stats from bin
        cur.execute("""
            SELECT tier, COUNT(*), ROUND(AVG(final_score)::numeric, 4)
            FROM bin WHERE tier IS NOT NULL AND final_score > 0
            GROUP BY tier
        """)
        tier_stats = {}
        for tier, count, mean in cur.fetchall():
            tier_stats[tier] = {"count": count, "mean": float(mean)}

        # Recent deeds from bin (last 200 for visualization)
        cur.execute("""
            SELECT b.id, b.final_score, b.tier, b.domain_id, b.deed_id, b.scored_at
            FROM bin b
            WHERE b.status = 'scored' AND b.final_score > 0
            ORDER BY b.id DESC LIMIT 200
        """)
        for bid, score, tier, domain, deed_id, scored_at in cur.fetchall():
            deed_node_id = f"deed:{deed_id or f'BIN-{bid}'}"
            nodes.append({
                "id": deed_node_id,
                "type": "deed",
                "properties": {
                    "final_score": float(score) if score else 0,
                    "tier": tier,
                    "domain": domain,
                    "deeded": deed_id is not None,
                    "sealed_at": scored_at.isoformat() if scored_at else None,
                }
            })
            # Edges: deed → domain, deed → judges
            edges.append({"source": deed_node_id, "target": f"domain:{domain}", "type": "belongs_to"})
            if tier:
                edges.append({"source": deed_node_id, "target": "judge:gemma3:12b", "type": "scored_by"})
                edges.append({"source": deed_node_id, "target": "judge:gemma3:12b", "type": "scored_by"})

        # Anchor nodes
        cur.execute("SELECT COUNT(*) FROM anchors")
        anchor_count = cur.fetchone()[0]

        # Deed writer progress
        cur.execute("SELECT COUNT(*) FROM bin WHERE deed_id IS NOT NULL")
        deeds_written = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM bin WHERE status = 'scored'")
        total_scored = cur.fetchone()[0]

        conn.close()

        return {
            "name": "swarm-and-bee",
            "version": "1.0",
            "live": True,
            "summary": {
                "total_nodes": len(nodes),
                "total_edges": len(edges),
                "node_types": {},
                "tier_distribution": tier_stats,
            },
            "nodes": nodes,
            "edges": edges,
            "stats": {
                "pairs_in_db": sum(n["properties"].get("pairs", 0) for n in nodes if n["type"] == "domain"),
                "total_scored": total_scored,
                "deeds_written": deeds_written,
                "anchors": anchor_count,
            },
        }
    except Exception as e:
        return {"error": str(e), "live": False}


def get_full_status():
    """Complete system status for the main dashboard."""
    return {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "gpus": get_gpu_status(),
        "cooks": get_cook_status(),
        "fleet": get_fleet_status(),
        "database": get_db_stats(),
        "storage": get_storage(),
    }


# ─── HTTP SERVER ───

class OpsHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = urlparse(self.path).path.rstrip("/")

        routes = {
            "/ops/status": get_full_status,
            "/ops/gpus": get_gpu_status,
            "/ops/cook": get_cook_status,
            "/ops/fleet": get_fleet_status,
            "/ops/db": get_db_stats,
            "/ops/storage": get_storage,
            "/ops/graph": get_live_graph,
        }

        handler = routes.get(path)
        if handler:
            data = handler()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Cache-Control", "no-cache, max-age=5")
            self.end_headers()
            self.wfile.write(json.dumps(data, indent=2).encode())
        elif path == "/ops" or path == "":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({
                "service": "SwarmOps API",
                "version": "1.0",
                "endpoints": list(routes.keys()),
            }).encode())
        else:
            self.send_response(404)
            self.end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def log_message(self, fmt, *args):
        print(f"[ops] {self.client_address[0]} {args[0]}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SwarmOps API")
    parser.add_argument("--port", type=int, default=9090)
    args = parser.parse_args()

    print(f"[ops] SwarmOps API starting on :{args.port}")
    print(f"[ops] Endpoints: /ops/status /ops/gpus /ops/cook /ops/fleet /ops/db /ops/storage")
    HTTPServer(("0.0.0.0", args.port), OpsHandler).serve_forever()
