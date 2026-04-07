#!/usr/bin/env python3
"""
Tribunal-Hash Mining Pool API — 2miners pattern for AI training data.

Same API shape as 2miners.com/api. Same economics. New asset class.
Miners (GPUs) weigh pairs on the tribunal scale. Deeds are blocks.
Merkle batches are sealed blocks. Hedera anchors are matured blocks.
Revenue from deed sales flows back to miners as block rewards.

The tribunal is a SCALE. The weight IS the value. Price per pound.

Endpoints:
  GET /pool/api/stats      — Pool-wide stats (hashrate, miners, blocks, difficulty)
  GET /pool/api/blocks     — Merkle batches (candidates, immature, matured)
  GET /pool/api/miners     — Active GPUs with hashrate
  GET /pool/api/payments   — Reward distributions from shop sales
  GET /pool/api/accounts/{gpu_id} — Per-GPU miner stats

Usage:
    DATABASE_URL="..." python3 pool_api.py --port 9094
"""
import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

from swarm_config import cfg

DB_URL = os.environ.get("DATABASE_URL", "")
KWH_RATE = float(os.environ.get("ELECTRICITY_RATE", "0.10"))

# Domain-Hash algorithm registry
ALGORITHMS = {
    "MedHash":   {"domain": "medical",      "difficulty": "HIGH",   "pair_type": "clinical"},
    "CREHash":   {"domain": "cre",          "difficulty": "MEDIUM", "pair_type": "underwriting"},
    "GrantHash": {"domain": "grants",       "difficulty": "MEDIUM", "pair_type": "narrative"},
    "LegalHash": {"domain": "legal",        "difficulty": "HIGH",   "pair_type": "regulatory"},
    "AvionHash": {"domain": "aviation",     "difficulty": "MEDIUM", "pair_type": "safety"},
    "WikiHash":  {"domain": "self_healing", "difficulty": "LOW",    "pair_type": "strategy"},
}

DOMAIN_TO_ALGO = {v["domain"]: k for k, v in ALGORITHMS.items()}


def get_conn():
    import psycopg2
    if not DB_URL:
        raise RuntimeError("DATABASE_URL not set")
    return psycopg2.connect(DB_URL, connect_timeout=10)


def get_gpu_power():
    """Get real-time GPU stats from nvidia-smi."""
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=index,name,power.draw,temperature.gpu,utilization.gpu,memory.used,memory.total,clocks.gr,clocks.mem",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5)
        gpus = []
        for line in result.stdout.strip().split("\n"):
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 9:
                gpus.append({
                    "index": int(parts[0]),
                    "name": parts[1],
                    "power_w": float(parts[2]),
                    "temp_c": int(parts[3]),
                    "util_pct": int(parts[4]),
                    "vram_used_mb": int(parts[5]),
                    "vram_total_mb": int(parts[6]),
                    "core_mhz": int(parts[7]),
                    "mem_mhz": int(parts[8]),
                })
        return gpus
    except Exception:
        return []


def json_response(handler, data, status=200):
    body = json.dumps(data, default=str).encode()
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.end_headers()
    handler.wfile.write(body)


class PoolHandler(BaseHTTPRequestHandler):

    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        params = parse_qs(parsed.query)

        try:
            if path == "/pool/api/stats":
                self.handle_stats(params)
            elif path == "/pool/api/blocks":
                self.handle_blocks(params)
            elif path == "/pool/api/miners":
                self.handle_miners()
            elif path == "/pool/api/payments":
                self.handle_payments()
            elif path.startswith("/pool/api/accounts/"):
                gpu_id = path.split("/pool/api/accounts/")[1].split("/")[0]
                if "/shares/" in path:
                    range_val = path.split("/shares/")[1]
                    self.handle_account_shares(gpu_id, range_val)
                else:
                    self.handle_account(gpu_id)
            else:
                json_response(self, {"error": "not found"}, 404)
        except Exception as e:
            print(f"[pool-api] ERROR: {e}")
            json_response(self, {"error": str(e)}, 500)

    def handle_stats(self, params):
        """Pool-wide stats — mirrors 2miners /stats endpoint."""
        algo_filter = params.get("algorithm", [None])[0]
        conn = get_conn()
        cur = conn.cursor()

        # Total hashrate (deeds per hour, last hour)
        cur.execute("SELECT count(*) FROM deeds WHERE sealed_at > NOW() - INTERVAL '1 hour'")
        deeds_last_hour = cur.fetchone()[0]

        # Total deeds + batches
        cur.execute("SELECT count(*) FROM deeds")
        total_deeds = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM batches")
        total_batches = cur.fetchone()[0]

        # Batch maturity
        cur.execute("SELECT count(*) FROM batches WHERE id NOT IN (SELECT batch_id FROM anchors WHERE batch_id IS NOT NULL)")
        immature_batches = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM anchors WHERE status = 'confirmed'")
        matured_batches = cur.fetchone()[0]
        candidates = total_batches - immature_batches - matured_batches

        # Per-algorithm stats
        cur.execute("""
            SELECT domain_id, count(*),
                   count(*) FILTER (WHERE tier = 'royal_jelly'),
                   count(*) FILTER (WHERE tier = 'honey'),
                   count(*) FILTER (WHERE tier = 'propolis'),
                   round(avg(final_score)::numeric, 4),
                   count(*) FILTER (WHERE sealed_at > NOW() - INTERVAL '1 hour')
            FROM deeds GROUP BY domain_id
        """)
        algorithms = {}
        for dom, total, rj, honey, prop, avg_s, hr in cur.fetchall():
            algo = DOMAIN_TO_ALGO.get(dom, dom)
            class_a_yield = round(rj / max(total, 1) * 100, 1)
            algorithms[algo] = {
                "domain": dom,
                "totalDeeds": total,
                "hashrate": hr,
                "difficulty": round(100 - class_a_yield, 1),
                "classA": rj,
                "classB": honey,
                "classC": prop,
                "avgWeight": float(avg_s or 0),
                "classAYield": class_a_yield,
                "totalWeight": round(float(avg_s or 0) * total, 1),
                "pricePerPound": 0.029,
            }

        # Hashrate chart (last 24h)
        cur.execute("""
            SELECT date_trunc('hour', sealed_at) as hr, count(*)
            FROM deeds WHERE sealed_at > NOW() - INTERVAL '24 hours'
            GROUP BY 1 ORDER BY 1
        """)
        pool_charts = [{"x": int(h.timestamp()), "y": c} for h, c in cur.fetchall()]

        # Last block (batch) found
        cur.execute("SELECT created_at FROM batches ORDER BY created_at DESC LIMIT 1")
        last_batch = cur.fetchone()

        # Miners count
        gpus = get_gpu_power()
        miners_online = len([g for g in gpus if g["util_pct"] > 5])

        # GPU power
        gpu_total_w = sum(g["power_w"] for g in gpus)
        fleet_w = gpu_total_w + 200 + 50 + 125 + 40  # whale + edge + cpu/2 + nas

        conn.close()

        json_response(self, {
            "hashrate": deeds_last_hour,
            "hashrateUnit": "deeds/hr",
            "minersTotal": miners_online + 1,  # +1 for whale
            "workersTotal": miners_online + 1,
            "candidatesTotal": max(candidates, 0),
            "immatureTotal": immature_batches,
            "maturedTotal": matured_batches,
            "now": int(time.time()),
            "stats": {
                "lastBlockFound": int(last_batch[0].timestamp()) if last_batch else 0,
                "roundShares": total_deeds % 50,
                "totalDeeds": total_deeds,
                "totalBatches": total_batches,
            },
            "algorithms": algorithms,
            "poolCharts": pool_charts,
            "fleet": {
                "totalWatts": round(fleet_w, 1),
                "costPerHour": round(fleet_w / 1000 * KWH_RATE, 4),
                "costPerDeed": round((fleet_w / max(deeds_last_hour, 1)) / 1000 * KWH_RATE, 8),
                "gpus": gpus,
            },
            "nodes": [
                {"name": "swarmrails", "status": "online", "gpus": len(gpus)},
                {"name": "whale", "status": "online", "gpus": 1},
                {"name": "edge", "status": "online", "role": "recorder"},
            ],
        })

    def handle_blocks(self, params):
        """Merkle batches as mining blocks — mirrors 2miners /blocks."""
        conn = get_conn()
        cur = conn.cursor()

        # Candidates (open batches — deeds without batch)
        cur.execute("SELECT count(*) FROM deeds WHERE batch_id IS NULL")
        pending_deeds = cur.fetchone()[0]

        # Immature (batched but not anchored)
        cur.execute("""
            SELECT b.id, b.merkle_root, b.leaf_count, b.domain_id, b.created_at
            FROM batches b
            WHERE b.id NOT IN (SELECT batch_id FROM anchors WHERE batch_id IS NOT NULL)
            ORDER BY b.created_at DESC LIMIT 50
        """)
        immature = [{"id": r[0], "merkle_root": r[1], "leaf_count": r[2],
                      "domain": r[3], "timestamp": r[4], "status": "immature"} for r in cur.fetchall()]

        # Matured (anchored to Hedera)
        cur.execute("""
            SELECT b.id, b.merkle_root, b.leaf_count, b.domain_id, b.created_at,
                   a.hedera_topic, a.hedera_sequence, a.hedera_timestamp
            FROM batches b JOIN anchors a ON a.batch_id = b.id
            WHERE a.status = 'confirmed'
            ORDER BY b.created_at DESC LIMIT 50
        """)
        matured = [{"id": r[0], "merkle_root": r[1], "leaf_count": r[2],
                     "domain": r[3], "timestamp": r[4], "hedera_topic": r[5],
                     "hedera_sequence": r[6], "hedera_timestamp": r[7],
                     "status": "matured"} for r in cur.fetchall()]

        conn.close()

        json_response(self, {
            "candidates": [{"pendingDeeds": pending_deeds, "targetSize": 50}],
            "candidatesTotal": 1 if pending_deeds > 0 else 0,
            "immature": immature,
            "immatureTotal": len(immature),
            "matured": matured,
            "maturedTotal": len(matured),
        })

    def handle_miners(self):
        """Active GPUs — mirrors 2miners /miners."""
        gpus = get_gpu_power()
        conn = get_conn()
        cur = conn.cursor()

        # Get per-judge deed counts
        cur.execute("""
            SELECT judge_a_id, count(*) FROM deeds GROUP BY judge_a_id
            UNION ALL
            SELECT judge_b_id, count(*) FROM deeds GROUP BY judge_b_id
        """)
        judge_deeds = {}
        for jid, cnt in cur.fetchall():
            judge_deeds[jid] = judge_deeds.get(jid, 0) + cnt

        conn.close()

        miners = {}
        for gpu in gpus:
            gpu_id = f"gpu{gpu['index']}"
            role = "training" if gpu["index"] == 0 else "judge_a"
            miners[gpu_id] = {
                "name": gpu["name"],
                "lastBeat": int(time.time()),
                "hashrate": gpu["util_pct"],
                "power_w": gpu["power_w"],
                "temp_c": gpu["temp_c"],
                "core_mhz": gpu["core_mhz"],
                "mem_mhz": gpu["mem_mhz"],
                "vram_used_mb": gpu["vram_used_mb"],
                "vram_total_mb": gpu["vram_total_mb"],
                "role": role,
                "offline": gpu["util_pct"] == 0,
            }

        # Add whale
        miners["whale"] = {
            "name": "RTX 3090 (192.168.0.99)",
            "lastBeat": int(time.time()),
            "role": "judge_b",
            "offline": False,
            "deeds_scored": judge_deeds.get(cfg.scale_b_model, 0),
        }

        json_response(self, {
            "hashrate": sum(g["power_w"] for g in gpus),
            "miners": miners,
            "minersTotal": len(miners),
            "now": int(time.time()),
        })

    def handle_payments(self):
        """Reward distributions — mirrors 2miners /payments."""
        # For now, calculate theoretical payments from deed inventory
        conn = get_conn()
        cur = conn.cursor()

        cur.execute("""
            SELECT domain_id, count(*) FILTER (WHERE final_score >= %s) as class_a
            FROM deeds GROUP BY domain_id
        """, (cfg.rj_threshold,))
        domains = dict(cur.fetchall())
        conn.close()

        # Calculate potential revenue at $29/1000 lbs Class A weight
        payments = []
        total_value = 0
        for dom, class_a_count in domains.items():
            packages = class_a_count // 1000
            value = packages * 29
            total_value += value
            if packages > 0:
                algo = DOMAIN_TO_ALGO.get(dom, dom)
                payments.append({
                    "algorithm": algo,
                    "domain": dom,
                    "classAWeight": class_a_count,
                    "packages": packages,
                    "pricePerPound": 0.029,
                    "value_usd": value,
                    "status": "harvestable",
                })

        json_response(self, {
            "payments": payments,
            "paymentsTotal": len(payments),
            "totalValue": total_value,
            "rewardModel": {
                "judgeA_pct": 40,
                "judgeB_pct": 30,
                "recorder_pct": 10,
                "infrastructure_pct": 20,
            },
        })

    def handle_account(self, gpu_id):
        """Per-GPU miner stats — mirrors 2miners /accounts/{walletid}."""
        conn = get_conn()
        cur = conn.cursor()

        # Map gpu_id to judge model
        judge_map = {
            "gpu0": None,  # training, not a judge
            "gpu1": cfg.scale_a_model,
            "whale": cfg.scale_b_model,
        }
        judge_model = judge_map.get(gpu_id)

        if judge_model:
            # Get deed stats for this judge
            cur.execute("""
                SELECT count(*), round(avg(final_score)::numeric, 4),
                       count(*) FILTER (WHERE tier = 'royal_jelly'),
                       count(*) FILTER (WHERE sealed_at > NOW() - INTERVAL '1 hour'),
                       count(*) FILTER (WHERE sealed_at > NOW() - INTERVAL '24 hours')
                FROM deeds WHERE judge_a_id = %s OR judge_b_id = %s
            """, (judge_model, judge_model))
            total, avg_score, rj, last_hr, last_24h = cur.fetchone()

            # Per-algorithm breakdown
            cur.execute("""
                SELECT domain_id, count(*),
                       count(*) FILTER (WHERE tier = 'royal_jelly')
                FROM deeds WHERE judge_a_id = %s OR judge_b_id = %s
                GROUP BY domain_id
            """, (judge_model, judge_model))
            sumrewards = [{"algorithm": DOMAIN_TO_ALGO.get(d, d), "deeds": c, "rj": r}
                          for d, c, r in cur.fetchall()]
        else:
            total = avg_score = rj = last_hr = last_24h = 0
            sumrewards = []

        conn.close()

        # Get GPU power stats
        gpus = get_gpu_power()
        gpu_info = next((g for g in gpus if f"gpu{g['index']}" == gpu_id), None)

        json_response(self, {
            "gpu_id": gpu_id,
            "judge_model": judge_model,
            "currentHashrate": last_hr,
            "hashrate": round(total / max(1, 1), 1),  # lifetime
            "stats": {
                "totalDeeds": total,
                "avgScore": float(avg_score or 0),
                "royalJelly": rj,
                "last24h": last_24h,
            },
            "workersOnline": 1 if gpu_info and gpu_info["util_pct"] > 5 else 0,
            "sumrewards": sumrewards,
            "gpu": gpu_info,
            "24hreward": last_24h,
        })

    def handle_account_shares(self, gpu_id, range_val):
        """Share statistics by time range — mirrors 2miners shares endpoint."""
        range_map = {"5m": "5 minutes", "30m": "30 minutes", "6h": "6 hours"}
        interval = range_map.get(range_val, "30 minutes")

        judge_map = {"gpu1": cfg.scale_a_model, "whale": cfg.scale_b_model}
        judge_model = judge_map.get(gpu_id)

        if not judge_model:
            json_response(self, {"shares": [], "error": "no judge on this GPU"})
            return

        conn = get_conn()
        cur = conn.cursor()
        cur.execute(f"""
            SELECT count(*) FILTER (WHERE tier = 'royal_jelly') as valid,
                   count(*) FILTER (WHERE tier = 'honey') as stale,
                   count(*) FILTER (WHERE tier = 'propolis') as invalid,
                   count(*) as total
            FROM deeds
            WHERE (judge_a_id = %s OR judge_b_id = %s)
              AND sealed_at > NOW() - INTERVAL '{interval}'
        """, (judge_model, judge_model))
        rj, honey, prop, total = cur.fetchone()
        conn.close()

        json_response(self, {
            "shares": [{
                "classA": rj,
                "classB": honey,
                "classC": prop,
                "total": total,
                "range": range_val,
                "x": int(time.time()),
            }],
        })

    def log_message(self, format, *args):
        print(f"[pool-api] {args[0]}" if args else "")


def serve(port=9094):
    if not DB_URL:
        print("[FATAL] DATABASE_URL not set")
        sys.exit(1)
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT count(*) FROM deeds")
    count = cur.fetchone()[0]
    conn.close()
    print(f"[pool-api] Tribunal-Hash Mining Pool API")
    print(f"[pool-api] {count:,} deeds mined | Serving on :{port}")
    print(f"[pool-api] Algorithms: {', '.join(ALGORITHMS.keys())}")
    HTTPServer(("0.0.0.0", port), PoolHandler).serve_forever()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=9094)
    serve(parser.parse_args().port)
