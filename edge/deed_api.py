#!/usr/bin/env python3
"""
SwarmDeed Live API — real-time weight certificate queries from PostgreSQL.

Lightweight HTTP server for the County Recorder's Office.
Every deed is a weight certificate — dual-scale consensus, Merkle-sealed,
blockchain-anchored. Queryable in real time. Price per pound.
Runs on Zima Lite (.173) behind nginx reverse proxy.

Endpoints:
  GET /deed/api/stats      — overview stats
  GET /deed/api/deeds      — paginated deed list (?limit=50&offset=0&tier=&domain=&q=)
  GET /deed/api/deed/<id>  — single deed with pair preview
  GET /deed/api/batches    — Merkle batch list
  GET /deed/api/finality   — pipeline status

Usage:
    DATABASE_URL="postgresql://..." python3 deed_api.py --port 9091
"""
import argparse
import json
import os
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs


DB_URL = os.environ.get("DATABASE_URL", "")


def get_conn():
    import psycopg2
    if not DB_URL:
        raise RuntimeError("DATABASE_URL not set")
    return psycopg2.connect(DB_URL, connect_timeout=10)


def json_response(handler, data, status=200):
    body = json.dumps(data, default=str).encode()
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.end_headers()
    handler.wfile.write(body)


class DeedHandler(BaseHTTPRequestHandler):

    def do_HEAD(self):
        """Support HEAD requests (Cloudflare probes)."""
        self.do_GET()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        params = parse_qs(parsed.query)

        try:
            if path == "/deed/api/stats":
                self.handle_stats()
            elif path == "/deed/api/deeds":
                self.handle_deeds(params)
            elif path.startswith("/deed/api/deed/"):
                deed_id = path.split("/deed/api/deed/")[1]
                self.handle_deed(deed_id)
            elif path == "/deed/api/batches":
                self.handle_batches()
            elif path == "/deed/api/finality":
                self.handle_finality()
            elif path == "/deed/api/domains":
                self.handle_domains()
            elif path == "/deed/api/quality":
                self.handle_quality()
            elif path == "/deed/api/energy":
                self.handle_energy()
            elif path == "/deed/api/download-ledger":
                self.handle_download_ledger(params)
            else:
                json_response(self, {"error": "not found"}, 404)
        except Exception as e:
            print(f"[api] ERROR: {e}")
            json_response(self, {"error": str(e)}, 500)

    def handle_stats(self):
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT count(*) FROM deeds")
        total = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM batches")
        batches = cur.fetchone()[0]
        cur.execute("SELECT tier, count(*) FROM deeds GROUP BY tier ORDER BY 2 DESC")
        tiers = {t.replace("_", "-"): c for t, c in cur.fetchall()}
        cur.execute("SELECT domain_id, count(*) FROM deeds GROUP BY domain_id ORDER BY 2 DESC")
        domains = dict(cur.fetchall())
        cur.execute("SELECT avg(final_score), min(final_score), max(final_score) FROM deeds WHERE final_score > 0")
        avg_s, min_s, max_s = cur.fetchone()
        cur.execute("SELECT count(*) FROM bin WHERE status = 'scored'")
        remaining = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM bin WHERE status = 'flagged'")
        flagged = cur.fetchone()[0]
        conn.close()
        json_response(self, {
            "total": total, "batches": batches, "remaining": remaining, "flagged": flagged,
            "tiers": tiers, "domains": domains,
            "avg_score": round(float(avg_s or 0), 4),
            "min_score": round(float(min_s or 0), 4),
            "max_score": round(float(max_s or 0), 4),
        })

    def handle_deeds(self, params):
        limit = min(int(params.get("limit", [50])[0]), 200)
        offset = int(params.get("offset", [0])[0])
        tier = params.get("tier", [None])[0]
        domain = params.get("domain", [None])[0]
        q = params.get("q", [None])[0]

        conn = get_conn()
        cur = conn.cursor()

        where = ["1=1"]
        args = []
        if tier:
            where.append("d.tier = %s")
            args.append(tier.replace("-", "_"))
        if domain:
            where.append("d.domain_id = %s")
            args.append(domain)

        where_sql = " AND ".join(where)

        if q:
            cur.execute(f"""
                SELECT d.id, d.domain_id, d.tier, d.final_score, d.judge_a_score, d.judge_b_score,
                       d.batch_id, d.sealed_at, LEFT(d.judge_a_reasoning, 150), LEFT(d.judge_b_reasoning, 150),
                       LEFT(p.fingerprint, 16), p.char_count
                FROM deeds d JOIN pairs p ON p.id = d.pair_id
                WHERE {where_sql}
                  AND (d.id ILIKE %s OR d.judge_a_reasoning ILIKE %s OR d.judge_b_reasoning ILIKE %s)
                ORDER BY d.sealed_at DESC LIMIT %s OFFSET %s
            """, args + [f"%{q}%", f"%{q}%", f"%{q}%", limit, offset])
        else:
            cur.execute(f"""
                SELECT d.id, d.domain_id, d.tier, d.final_score, d.judge_a_score, d.judge_b_score,
                       d.batch_id, d.sealed_at, LEFT(d.judge_a_reasoning, 150), LEFT(d.judge_b_reasoning, 150),
                       LEFT(p.fingerprint, 16), p.char_count
                FROM deeds d JOIN pairs p ON p.id = d.pair_id
                WHERE {where_sql}
                ORDER BY d.sealed_at DESC LIMIT %s OFFSET %s
            """, args + [limit, offset])

        rows = cur.fetchall()
        cur.execute(f"SELECT count(*) FROM deeds d WHERE {where_sql}", args)
        total = cur.fetchone()[0]
        conn.close()

        deeds = []
        for r in rows:
            deeds.append({
                "deed_id": r[0], "domain": r[1], "tier": (r[2] or "").replace("_", "-"),
                "final_score": r[3], "score_a": r[4], "score_b": r[5],
                "batch_id": r[6], "sealed_at": r[7],
                "reasoning_a": r[8], "reasoning_b": r[9],
                "fingerprint": r[10], "char_count": r[11],
            })
        json_response(self, {"deeds": deeds, "total": total, "limit": limit, "offset": offset})

    def handle_deed(self, deed_id):
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("""
            SELECT d.*, p.fingerprint, p.char_count, p.messages
            FROM deeds d JOIN pairs p ON p.id = d.pair_id
            WHERE d.id = %s
        """, (deed_id,))
        row = cur.fetchone()
        if not row:
            conn.close()
            json_response(self, {"error": f"Deed {deed_id} not found"}, 404)
            return

        cols = [desc[0] for desc in cur.description]
        d = dict(zip(cols, row))
        # Parse messages for preview
        msgs = d.get("messages", [])
        if isinstance(msgs, str):
            msgs = json.loads(msgs)
        d["system_preview"] = next((m["content"][:150] for m in msgs if m.get("role") == "system"), "")
        d["user_preview"] = next((m["content"][:300] for m in msgs if m.get("role") == "user"), "")
        d["assistant_preview"] = next((m["content"][:300] for m in msgs if m.get("role") == "assistant"), "")
        del d["messages"]  # Don't send full messages over API
        d["tier"] = (d.get("tier") or "").replace("_", "-")
        conn.close()
        json_response(self, d)

    def handle_batches(self):
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT id, merkle_root, leaf_count, block_range, domain_id, created_at FROM batches ORDER BY created_at DESC")
        rows = cur.fetchall()
        conn.close()
        batches = [{"batch_id": r[0], "merkle_root": r[1], "leaf_count": r[2],
                     "block_range": r[3], "domain": r[4], "created_at": r[5]} for r in rows]
        json_response(self, {"batches": batches, "total": len(batches)})

    def handle_finality(self):
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT count(*) FROM deeds")
        deeds = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM batches")
        batches = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM anchors")
        anchors = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM bin WHERE status = 'scored'")
        remaining = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM bin WHERE status = 'deeded'")
        deeded = cur.fetchone()[0]
        conn.close()
        json_response(self, {
            "l1_postgresql": {"status": "active", "deeds": deeds, "deeded_in_bin": deeded},
            "l2_merkle": {"status": "active" if batches > 0 else "pending", "batches": batches},
            "l3_ipfs": {"status": "pending"},
            "l4_hedera": {"status": "active" if anchors > 0 else "pending", "anchors": anchors, "topic": "0.0.10291838"},
            "l5_ens": {"status": "active", "domain": "swarmdeed.eth"},
            "pipeline": {"filed": deeds, "remaining": remaining, "pct": round(deeds / max(deeds + remaining, 1) * 100, 1)},
        })

    def handle_quality(self):
        """Quality dashboard — score distribution, judge agreement, throughput, live feed."""
        conn = get_conn()
        cur = conn.cursor()

        # Score distribution
        cur.execute("""
            SELECT CASE
                WHEN final_score >= 0.90 THEN '0.90+'
                WHEN final_score >= 0.85 THEN '0.85-0.89'
                WHEN final_score >= 0.80 THEN '0.80-0.84'
                WHEN final_score >= 0.70 THEN '0.70-0.79'
                ELSE 'below_0.70'
            END as bucket, count(*)
            FROM deeds GROUP BY 1 ORDER BY 1
        """)
        score_dist = dict(cur.fetchall())

        # Judge agreement
        cur.execute("""
            SELECT round(avg(abs(judge_a_score - judge_b_score))::numeric, 4),
                   round(max(abs(judge_a_score - judge_b_score))::numeric, 4),
                   count(*) FILTER (WHERE abs(judge_a_score - judge_b_score) > 0.20)
            FROM deeds
        """)
        agree = cur.fetchone()

        # Throughput (last 12 hours)
        cur.execute("""
            SELECT date_trunc('hour', sealed_at) as hr, count(*)
            FROM deeds WHERE sealed_at > NOW() - INTERVAL '12 hours'
            GROUP BY 1 ORDER BY 1
        """)
        throughput = [{"hour": str(h), "count": c} for h, c in cur.fetchall()]

        # Latest 10 deeds (live feed)
        cur.execute("""
            SELECT d.id, d.domain_id, d.tier, d.final_score, d.judge_a_score, d.judge_b_score,
                   d.max_drift, d.sealed_at, LEFT(d.judge_a_reasoning, 100), LEFT(d.judge_b_reasoning, 100)
            FROM deeds d ORDER BY d.sealed_at DESC LIMIT 10
        """)
        live = [{"deed_id": r[0], "domain": r[1], "tier": (r[2] or "").replace("_", "-"),
                 "score": r[3], "score_a": r[4], "score_b": r[5], "drift": r[6],
                 "sealed_at": r[7], "reason_a": r[8], "reason_b": r[9]} for r in cur.fetchall()]

        # Per-domain quality
        cur.execute("""
            SELECT domain_id, count(*), round(avg(final_score)::numeric, 4),
                   count(*) FILTER (WHERE tier = 'royal_jelly'),
                   count(*) FILTER (WHERE tier = 'honey'),
                   count(*) FILTER (WHERE tier = 'propolis')
            FROM deeds GROUP BY domain_id ORDER BY 2 DESC
        """)
        domains = [{"domain": r[0], "total": r[1], "avg_score": float(r[2] or 0),
                     "rj": r[3], "honey": r[4], "propolis": r[5]} for r in cur.fetchall()]

        conn.close()
        json_response(self, {
            "score_distribution": score_dist,
            "judge_agreement": {"avg_gap": float(agree[0] or 0), "max_gap": float(agree[1] or 0), "high_disagreement": agree[2]},
            "throughput": throughput,
            "live_feed": live,
            "domains": domains,
        })

    def handle_energy(self):
        """Live energy economics — fleet power, cost per deed, efficiency."""
        conn = get_conn()
        cur = conn.cursor()

        # Get deed count and rate from last hour
        cur.execute("SELECT count(*) FROM deeds WHERE sealed_at > NOW() - INTERVAL '1 hour'")
        deeds_last_hour = cur.fetchone()[0]

        cur.execute("SELECT count(*) FROM deeds")
        total_deeds = cur.fetchone()[0]

        cur.execute("SELECT count(*) FROM batches")
        total_batches = cur.fetchone()[0]

        conn.close()

        # Energy calculations (fleet estimates + real GPU data via proxy)
        # Zima Lite can't query nvidia-smi directly, so use measured averages
        gpu0_w = 300  # cooking (constant)
        gpu1_w = 240  # tribunal (avg during scoring)
        whale_w = 200  # judge B
        edge_w = 50
        cpu_w = 250
        nas_w = 40
        fleet_w = gpu0_w + gpu1_w + whale_w + edge_w + cpu_w + nas_w
        tribunal_w = gpu1_w + whale_w + edge_w + cpu_w / 2

        rate = max(deeds_last_hour, 1)
        wh_per_deed = tribunal_w / rate
        cost_per_deed = (wh_per_deed / 1000) * 0.10

        json_response(self, {
            "fleet": {
                "total_watts": fleet_w,
                "gpu0": {"watts": gpu0_w, "role": "cooking Gemma 4 31B"},
                "gpu1": {"watts": gpu1_w, "role": "Judge A (gemma3:12b)"},
                "whale": {"watts": whale_w, "role": "idle"},
                "edge": {"watts": edge_w, "role": "deed recorder + watchdog"},
                "cpu": {"watts": cpu_w, "role": "Xeon w9-3475X"},
                "nas": {"watts": nas_w, "role": "PostgreSQL + storage"},
            },
            "economics": {
                "cost_per_hour": round(fleet_w / 1000 * 0.10, 4),
                "cost_per_day": round(fleet_w / 1000 * 0.10 * 24, 2),
                "cost_per_deed": round(cost_per_deed, 8),
                "wh_per_deed": round(wh_per_deed, 4),
                "pairs_per_kwh": round(rate / max(tribunal_w / 1000, 0.001), 1),
                "deeds_last_hour": deeds_last_hour,
                "kwh_rate": 0.10,
            },
            "totals": {
                "total_deeds": total_deeds,
                "total_batches": total_batches,
                "total_energy_kwh": round(total_deeds * wh_per_deed / 1000, 2),
                "total_cost": round(total_deeds * cost_per_deed, 4),
            },
        })

    def handle_domains(self):
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("""
            SELECT d.domain_id,
                   count(*) as total,
                   count(*) FILTER (WHERE d.tier = 'royal_jelly') as rj,
                   count(*) FILTER (WHERE d.tier = 'honey') as honey,
                   count(*) FILTER (WHERE d.tier = 'propolis') as propolis,
                   avg(d.final_score) as avg_score
            FROM deeds d GROUP BY d.domain_id ORDER BY count(*) DESC
        """)
        rows = cur.fetchall()
        conn.close()
        domains = [{"domain": r[0], "total": r[1], "royal_jelly": r[2], "honey": r[3],
                     "propolis": r[4], "avg_score": round(float(r[5] or 0), 4)} for r in rows]
        json_response(self, {"domains": domains})

    def handle_download_ledger(self, params):
        """Stream full deed ledger as CSV — always current from PostgreSQL."""
        import csv
        import io

        fmt = params.get("format", ["csv"])[0]
        tier_filter = params.get("tier", [None])[0]
        domain_filter = params.get("domain", [None])[0]

        conn = get_conn()
        cur = conn.cursor()

        where = ["1=1"]
        args = []
        if tier_filter:
            where.append("d.tier = %s")
            args.append(tier_filter.replace("-", "_"))
        if domain_filter:
            where.append("d.domain_id = %s")
            args.append(domain_filter)

        cur.execute(f"""
            SELECT d.id, d.domain_id, d.tier, d.final_score,
                   d.judge_a_id, d.judge_a_score, d.judge_b_id, d.judge_b_score,
                   d.max_drift, d.batch_id, d.merkle_root, d.merkle_leaf_idx,
                   d.sealed_at, d.validated,
                   LEFT(d.judge_a_reasoning, 300), LEFT(d.judge_b_reasoning, 300),
                   p.fingerprint, p.char_count, p.domain_id
            FROM deeds d LEFT JOIN pairs p ON p.id = d.pair_id
            WHERE {" AND ".join(where)}
            ORDER BY d.sealed_at DESC
        """, args)

        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow([
            "deed_id", "domain", "tier", "final_score",
            "judge_a_id", "judge_a_score", "judge_b_id", "judge_b_score",
            "max_drift", "batch_id", "merkle_root", "merkle_leaf_idx",
            "sealed_at", "validated",
            "judge_a_reasoning", "judge_b_reasoning",
            "fingerprint", "char_count", "pair_domain",
        ])
        count = 0
        for row in cur:
            writer.writerow(row)
            count += 1

        conn.close()
        body = buf.getvalue().encode("utf-8")

        from datetime import datetime
        ts = datetime.now().strftime("%Y%m%d_%H%M")
        filename = f"swarmdeed_ledger_{count}_deeds_{ts}.csv"

        self.send_response(200)
        self.send_header("Content-Type", "text/csv; charset=utf-8")
        self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)
        print(f"[deed-api] Ledger download: {count} deeds → {filename}")

    def log_message(self, format, *args):
        print(f"[deed-api] {args[0]}" if args else "")


def serve(port=9091):
    if not DB_URL:
        print("[FATAL] DATABASE_URL not set")
        sys.exit(1)
    # Test connection
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT count(*) FROM deeds")
    count = cur.fetchone()[0]
    conn.close()
    print(f"[deed-api] Connected — {count:,} deeds in registry")
    print(f"[deed-api] Serving on :{port}")
    HTTPServer(("0.0.0.0", port), DeedHandler).serve_forever()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=9091)
    serve(parser.parse_args().port)
