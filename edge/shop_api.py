#!/usr/bin/env python3
"""
SwarmShop API — Dataset Marketplace with Stripe Checkout + Fulfillment
======================================================================
Packages only. Every package: 5 formats + deed certs + OM + quality report.

Endpoints:
  GET  /shop/api/catalog             — Domain cards with packages
  GET  /shop/api/preview/<domain>    — Sample pairs
  POST /shop/api/checkout            — Create Stripe checkout session
  POST /shop/api/webhook             — Stripe webhook (payment confirmed → fulfill)
  GET  /shop/api/download/<token>    — Secure download (ZIP, time-limited)
  GET  /shop/api/sales               — Sales ledger

Usage:
    STRIPE_SECRET_KEY="sk_..." STRIPE_WEBHOOK_SECRET="whsec_..." \
    DATABASE_URL="postgresql://..." python3 shop_api.py --port 9092
"""
import argparse
import csv
import hashlib
import hmac
import io
import json
import logging
import os
import secrets
import sys
import time
import urllib.request
import zipfile
from datetime import datetime, timedelta, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs

from swarm_config import cfg

logging.basicConfig(level=logging.INFO, format="%(asctime)s [shop] %(levelname)s %(message)s")
log = logging.getLogger("shop")

DB_URL = os.environ.get("DATABASE_URL", "")
STRIPE_KEY = os.environ.get("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
RESEND_KEY = os.environ.get("RESEND_API_KEY", "")
SHOP_URL = os.environ.get("SHOP_URL", "https://swarmandbee.ai/shop")
DOWNLOAD_DIR = Path(os.environ.get("DOWNLOAD_DIR", "/mnt/swarm/shop/downloads"))

# ── PRICE PER POUND (Class A — Royal Jelly) ──
# 20x cost to mint. Fleet: 500W, $0.15/kWh, real RJ/hr throughput.
# Adjust when market discovery provides validation.
PRICE_PER_LB = {
    "legal":     0.0022,
    "grants":    0.0061,
    "medical":   0.0072,
    "aviation":  0.0075,
    "agenthash": 0.016,
    "cre":       0.029,
    "clawhash":  0.048,
}

MIN_POUNDS = 100
MAX_POUNDS = 50000

DOMAIN_INFO = {
    "grants": "Master Writer — Federal grant writing, SBIR/STTR, NEA, DOE, NIH. Budget narratives, compliance, strategy. Powered by Gemma 4 31B.",
    "legal": "Legal & Regulatory — Consumer protection, FDCPA, CFPB, state regs. Citation-heavy compliance analysis.",
    "aviation": "Aviation safety, maintenance, ATC procedures. FAA/ICAO-aligned.",
    "cre": "Commercial real estate underwriting. Cap rates, NOI, DSCR, lease analysis.",
    "medical": "Board-certified medical Q&A. Radiology, pathology, clinical decision-making, drug interactions.",
    "agenthash": "AI Agent capabilities — tool use, recovery, security, structure, memory, eval, multi-step reasoning.",
    "clawhash": "Agent security — prompt injection defense, tool poisoning detection, RCE prevention, sandbox enforcement, audit trails.",
}


def get_conn():
    import psycopg2
    if not DB_URL:
        raise RuntimeError("DATABASE_URL not set")
    return psycopg2.connect(DB_URL, connect_timeout=10)


def json_resp(handler, data, status=200):
    body = json.dumps(data, default=str).encode()
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
    handler.send_header("Access-Control-Allow-Headers", "Content-Type, Stripe-Signature")
    handler.end_headers()
    handler.wfile.write(body)


def binary_resp(handler, data, filename, content_type="application/zip"):
    handler.send_response(200)
    handler.send_header("Content-Type", content_type)
    handler.send_header("Content-Disposition", f'attachment; filename="{filename}"')
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)


# ═══════════════════════════════════════════════════════
#  DATASET PACKAGER
# ═══════════════════════════════════════════════════════

def build_package(domain, pair_count, order_id):
    """Query DB, build all 5 formats + deeds + OM + manifest → ZIP bytes."""
    conn = get_conn()
    cur = conn.cursor()

    # Pull top Royal Jelly pairs by score
    limit = pair_count if pair_count > 0 else 999999
    cur.execute("""
        SELECT d.id, d.tier, d.final_score, d.judge_a_id, d.judge_a_score,
               d.judge_b_id, d.judge_b_score, d.judge_a_reasoning, d.judge_b_reasoning,
               d.batch_id, d.merkle_root, d.merkle_leaf_idx, d.sealed_at,
               p.messages, p.fingerprint, p.char_count
        FROM deeds d JOIN pairs p ON p.id = d.pair_id
        WHERE d.domain_id = %s AND d.tier = 'royal_jelly'
        ORDER BY d.final_score DESC
        LIMIT %s
    """, (domain, limit))
    rows = cur.fetchall()

    # Tier stats
    cur.execute("SELECT tier, count(*) FROM deeds WHERE domain_id = %s GROUP BY tier", (domain,))
    tier_stats = {t.replace("_", "-"): c for t, c in cur.fetchall()}

    # Score stats
    cur.execute("SELECT avg(final_score), min(final_score), max(final_score) FROM deeds WHERE domain_id = %s AND tier = 'royal_jelly'", (domain,))
    avg_s, min_s, max_s = cur.fetchone()
    conn.close()

    if not rows:
        return None, "No deeds available for this domain"

    actual_count = len(rows)

    # Parse all pairs
    pairs = []
    deeds = []
    for r in rows:
        msgs = r[13] if isinstance(r[13], list) else json.loads(r[13]) if r[13] else []
        sys_c = next((m["content"] for m in msgs if m.get("role") == "system"), "")
        usr_c = next((m["content"] for m in msgs if m.get("role") == "user"), "")
        ast_c = next((m["content"] for m in msgs if m.get("role") == "assistant"), "")

        pairs.append({"messages": msgs, "deed_id": r[0], "score": r[2], "fingerprint": r[14]})
        deeds.append({
            "deed_id": r[0], "tier": (r[1] or "").replace("_", "-"), "final_score": r[2],
            "judge_a": r[3], "score_a": r[4], "judge_b": r[5], "score_b": r[6],
            "reasoning_a": r[7], "reasoning_b": r[8],
            "batch_id": r[9], "merkle_root": r[10], "merkle_leaf_idx": r[11],
            "sealed_at": str(r[12]), "fingerprint": r[14], "char_count": r[15],
            "system_prompt": sys_c[:100], "user_query": usr_c[:200], "assistant_preview": ast_c[:200],
        })

    # ── BUILD FORMATS ──
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        prefix = f"swarmdeed-{domain}-{actual_count}"

        # 1. JSONL (chat format)
        jsonl = "\n".join(json.dumps({"messages": p["messages"]}, ensure_ascii=False) for p in pairs)
        zf.writestr(f"{prefix}/training_data.jsonl", jsonl)

        # 2. Parquet (as CSV — parquet needs pyarrow, CSV is universal fallback)
        csv_buf = io.StringIO()
        writer = csv.writer(csv_buf)
        writer.writerow(["deed_id", "score", "system", "user", "assistant", "fingerprint"])
        for p in pairs:
            msgs = p["messages"]
            writer.writerow([
                p["deed_id"], p["score"],
                next((m["content"] for m in msgs if m.get("role") == "system"), ""),
                next((m["content"] for m in msgs if m.get("role") == "user"), ""),
                next((m["content"] for m in msgs if m.get("role") == "assistant"), ""),
                p.get("fingerprint", ""),
            ])
        zf.writestr(f"{prefix}/training_data.csv", csv_buf.getvalue())

        # 3. Alpaca format
        alpaca = []
        for p in pairs:
            msgs = p["messages"]
            alpaca.append({
                "instruction": next((m["content"] for m in msgs if m.get("role") == "user"), ""),
                "input": next((m["content"] for m in msgs if m.get("role") == "system"), ""),
                "output": next((m["content"] for m in msgs if m.get("role") == "assistant"), ""),
            })
        zf.writestr(f"{prefix}/training_data_alpaca.json", json.dumps(alpaca, indent=2, ensure_ascii=False))

        # 4. ShareGPT format
        sharegpt = []
        for p in pairs:
            convos = []
            for m in p["messages"]:
                role_map = {"system": "system", "user": "human", "assistant": "gpt"}
                convos.append({"from": role_map.get(m["role"], m["role"]), "value": m["content"]})
            sharegpt.append({"conversations": convos})
        zf.writestr(f"{prefix}/training_data_sharegpt.json", json.dumps(sharegpt, indent=2, ensure_ascii=False))

        # 5. HuggingFace dataset format (JSONL with metadata)
        hf_lines = []
        for p in pairs:
            hf_lines.append(json.dumps({
                "messages": p["messages"],
                "metadata": {"deed_id": p["deed_id"], "score": p["score"], "fingerprint": p["fingerprint"]},
            }, ensure_ascii=False))
        zf.writestr(f"{prefix}/training_data_hf.jsonl", "\n".join(hf_lines))

        # 6. Deed certificates
        zf.writestr(f"{prefix}/deed_certificates.jsonl",
                     "\n".join(json.dumps(d, ensure_ascii=False) for d in deeds))

        # 7. Offering Memorandum
        om = f"""# Offering Memorandum — {domain.upper()} Dataset

## Swarm & Bee LLC — Defendable AI Training Data

**Order ID**: {order_id}
**Domain**: {domain.upper()}
**Package**: {actual_count:,} Royal Jelly pairs
**Generated**: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}

---

## What's In The Box

| Metric | Value |
|--------|-------|
| Total Pairs | {actual_count:,} |
| Tier | Royal Jelly (weight >= {cfg.rj_threshold}) |
| Average Score | {float(avg_s or 0):.4f} |
| Score Range | {float(min_s or 0):.4f} — {float(max_s or 0):.4f} |
| Scale A | {cfg.scale_a_model} (base, unmodified) |
| Scale B | {cfg.scale_b_model} (base, unmodified) |
| Weighing | 2-pass dual-scale tribunal. Drift threshold: {cfg.drift_threshold} |

## Domain Description

{DOMAIN_INFO.get(domain, domain + ' domain training data')}

## Quality Guarantee

Every pair in this package:
- Weighed by TWO independent base models on separate hardware (zero shared bias)
- Validated with 2-pass reproducibility check (drift <= 0.15)
- Filed as a formal deed with 5 proofs (Origin, Quality, Process, Economics, Trust)
- 5 weight dimensions: accuracy, completeness, specificity, structure, domain_expertise
- Batched into SHA256 Merkle trees (batch size: 50)
- Recorded in immutable PostgreSQL ledger

## Tier Distribution (full domain)

| Tier | Count | Percentage |
|------|-------|-----------|
| Royal Jelly (>= {cfg.rj_threshold}) | {tier_stats.get('royal-jelly', 0):,} | {tier_stats.get('royal-jelly', 0) / max(sum(tier_stats.values()), 1) * 100:.1f}% |
| Honey ({cfg.honey_threshold}-{cfg.rj_threshold - 0.01:.2f}) | {tier_stats.get('honey', 0):,} | {tier_stats.get('honey', 0) / max(sum(tier_stats.values()), 1) * 100:.1f}% |
| Propolis (< {cfg.honey_threshold}) | {tier_stats.get('propolis', 0):,} | {tier_stats.get('propolis', 0) / max(sum(tier_stats.values()), 1) * 100:.1f}% |

## Included Formats

1. `training_data.jsonl` — OpenAI/Anthropic chat format
2. `training_data.csv` — Spreadsheet-friendly
3. `training_data_alpaca.json` — Alpaca/LLaMA-Factory format
4. `training_data_sharegpt.json` — ShareGPT/chat-template format
5. `training_data_hf.jsonl` — HuggingFace datasets format
6. `deed_certificates.jsonl` — Full deed provenance for each pair
7. `offering_memorandum.md` — This document
8. `quality_report.json` — Machine-readable quality summary
9. `manifest.json` — Package metadata + checksums

## Provenance Chain

```
Pair → Dual-Judge Tribunal (2-pass) → Deed → Merkle Batch → PostgreSQL Ledger
```

Verify any deed at: https://swarmandbee.ai/deed/

## Contact

Swarm & Bee LLC
build@swarmandbee.ai
https://swarmandbee.ai
"""
        zf.writestr(f"{prefix}/offering_memorandum.md", om)

        # 8. Quality report (machine-readable)
        quality = {
            "order_id": order_id, "domain": domain, "pair_count": actual_count,
            "tier": "royal_jelly", "avg_score": float(avg_s or 0),
            "min_score": float(min_s or 0), "max_score": float(max_s or 0),
            "scales": [cfg.scale_a_model, cfg.scale_b_model], "weighing": "2-pass dual-scale tribunal",
            "drift_threshold": cfg.drift_threshold, "tier_distribution": tier_stats,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
        zf.writestr(f"{prefix}/quality_report.json", json.dumps(quality, indent=2))

        # 9. Manifest
        manifest = {
            "package": prefix, "order_id": order_id, "domain": domain,
            "pair_count": actual_count, "format_count": 5,
            "files": [
                "training_data.jsonl", "training_data.csv", "training_data_alpaca.json",
                "training_data_sharegpt.json", "training_data_hf.jsonl",
                "deed_certificates.jsonl", "offering_memorandum.md",
                "quality_report.json", "manifest.json",
            ],
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "checksum_sha256": hashlib.sha256(jsonl.encode()).hexdigest(),
        }
        zf.writestr(f"{prefix}/manifest.json", json.dumps(manifest, indent=2))

    zip_bytes = buf.getvalue()
    log.info("Package built: %s — %d pairs, %d bytes", prefix, actual_count, len(zip_bytes))
    return zip_bytes, actual_count


# ═══════════════════════════════════════════════════════
#  EMAIL DELIVERY
# ═══════════════════════════════════════════════════════

def send_delivery_email(email, domain, package_label, pair_count, download_url, order_id):
    if not RESEND_KEY:
        log.warning("No RESEND_API_KEY — delivery email not sent")
        return False
    try:
        html = f"""<html><body style="font-family:monospace;background:#0a0a0a;color:#e0e0e0;padding:30px;">
<div style="color:#d4a017;font-size:22px;border-bottom:2px solid #d4a017;padding-bottom:10px;">
SWARMDEED — ORDER CONFIRMED</div>
<div style="background:#111;border:1px solid #333;padding:15px;margin:15px 0;">
<table style="width:100%;border-collapse:collapse;">
<tr><td style="color:#888;padding:6px;">Order ID</td><td style="color:#4fc3f7;">{order_id}</td></tr>
<tr><td style="color:#888;padding:6px;">Domain</td><td>{domain.upper()}</td></tr>
<tr><td style="color:#888;padding:6px;">Package</td><td>{package_label}</td></tr>
<tr><td style="color:#888;padding:6px;">Pairs</td><td style="color:#d4a017;font-weight:bold;">{pair_count:,}</td></tr>
<tr><td style="color:#888;padding:6px;">Formats</td><td>JSONL, CSV, Alpaca, ShareGPT, HuggingFace</td></tr>
</table></div>
<div style="background:#111;border:1px solid #d4a017;padding:20px;margin:15px 0;text-align:center;">
<a href="{download_url}" style="color:#d4a017;font-size:16px;font-weight:bold;text-decoration:none;">
DOWNLOAD YOUR DATASET</a>
<div style="color:#555;font-size:11px;margin-top:8px;">Link expires in 72 hours. Contains all 5 formats + deed certificates + OM.</div>
</div>
<div style="color:#555;font-size:11px;margin-top:30px;text-align:center;">
Swarm & Bee LLC — Defendable AI Training Data<br>
Every pair scored. Every deed filed. Every proof verifiable.<br>
swarmandbee.ai</div>
</body></html>"""

        data = json.dumps({
            "from": "SwarmShop <build@swarmandbee.ai>",
            "to": [email],
            "subject": f"Your {domain.upper()} dataset is ready — {pair_count:,} pairs",
            "html": html,
        }).encode()
        req = urllib.request.Request("https://api.resend.com/emails", data=data,
                                     headers={"Authorization": f"Bearer {RESEND_KEY}", "Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=10)
        log.info("Delivery email sent to %s", email)
        return True
    except Exception as e:
        log.error("Email failed: %s", e)
        return False


# ═══════════════════════════════════════════════════════
#  FULFILLMENT
# ═══════════════════════════════════════════════════════

def fulfill_order(session_id, email, domain, package_key, amount_cents, pair_count=None):
    """Build package, store it, create download link, email buyer, record sale."""
    order_id = f"SW-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{secrets.token_hex(4).upper()}"
    if pair_count is None:
        pair_count = 1000  # fallback

    # Build
    zip_bytes, actual_count = build_package(domain, pair_count, order_id)
    if zip_bytes is None:
        log.error("Package build failed for %s/%s", domain, package_key)
        return None

    # Store
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    token = secrets.token_urlsafe(32)
    filename = f"{order_id}.zip"
    filepath = DOWNLOAD_DIR / filename
    filepath.write_bytes(zip_bytes)

    # Record sale
    conn = get_conn()
    cur = conn.cursor()
    expires = datetime.now(timezone.utc) + timedelta(hours=72)
    cur.execute("""
        INSERT INTO sales (id, stripe_session, buyer_email, domain, package, pair_count,
                          amount_cents, download_token, download_expires, status, fulfilled_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'fulfilled', NOW())
    """, (order_id, session_id, email, domain, package_key, actual_count,
          amount_cents, token, expires))
    conn.commit()
    conn.close()

    # Email
    price_per_lb = PRICE_PER_LB.get(domain, 1.99)
    label = f"{actual_count:,} lbs {domain.upper()} Class A @ ${price_per_lb:.2f}/lb"
    download_url = f"{SHOP_URL.rstrip('/')}/api/download/{token}"
    send_delivery_email(email, domain, label, actual_count, download_url, order_id)

    log.info("ORDER FULFILLED: %s — %s %s, %d pairs, $%.2f, token=%s",
             order_id, domain, package_key, actual_count, amount_cents / 100, token[:8])
    return {"order_id": order_id, "token": token, "download_url": download_url,
            "pairs": actual_count, "expires": expires.isoformat()}


# ═══════════════════════════════════════════════════════
#  HTTP HANDLER
# ═══════════════════════════════════════════════════════

class ShopHandler(BaseHTTPRequestHandler):

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Stripe-Signature")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        params = parse_qs(parsed.query)

        try:
            if path == "/shop/api/catalog":
                self.handle_catalog()
            elif path.startswith("/shop/api/preview/"):
                domain = path.split("/shop/api/preview/")[1]
                self.handle_preview(domain, params)
            elif path.startswith("/shop/api/download/"):
                token = path.split("/shop/api/download/")[1]
                self.handle_download(token)
            elif path == "/shop/api/sales":
                self.handle_sales()
            elif path == "/shop/api/free-sample":
                self.handle_free_sample(params)
            elif path.startswith("/shop/api/download-free/"):
                domain = path.split("/shop/api/download-free/")[1]
                self.handle_download_free(domain)
            else:
                json_resp(self, {"error": "not found"}, 404)
        except Exception as e:
            log.error("GET error: %s", e)
            json_resp(self, {"error": str(e)}, 500)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        try:
            length = int(self.headers.get("Content-Length", 0))
            raw_body = self.rfile.read(length) if length > 0 else b""

            if path == "/shop/api/checkout":
                body = json.loads(raw_body) if raw_body else {}
                self.handle_checkout(body)
            elif path == "/shop/api/webhook":
                self.handle_webhook(raw_body)
            else:
                json_resp(self, {"error": "not found"}, 404)
        except Exception as e:
            log.error("POST error: %s", e)
            json_resp(self, {"error": str(e)}, 500)

    # ── CATALOG ──
    def handle_catalog(self):
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("""
            SELECT d.domain_id, count(*) as deeds,
                   count(*) FILTER (WHERE d.tier = 'royal_jelly') as rj,
                   count(*) FILTER (WHERE d.tier = 'honey') as honey,
                   count(*) FILTER (WHERE d.tier = 'propolis') as propolis,
                   round(avg(d.final_score)::numeric, 4) as avg_score
            FROM deeds d GROUP BY d.domain_id ORDER BY count(*) DESC
        """)
        deed_stats = {r[0]: {"deeds": r[1], "rj": r[2], "honey": r[3], "propolis": r[4],
                              "avg_score": float(r[5] or 0)} for r in cur.fetchall()}
        cur.execute("SELECT domain_id, count(*) FROM pairs GROUP BY domain_id ORDER BY 2 DESC")
        pair_counts = dict(cur.fetchall())
        conn.close()

        # Include all registered domains (even those with 0 pairs)
        cur2 = get_conn()
        cur_dom = cur2.cursor()
        cur_dom.execute("SELECT id FROM domains ORDER BY id")
        all_domains = [r[0] for r in cur_dom.fetchall()]
        cur2.close()

        catalog = []
        for domain in sorted(set(list(pair_counts.keys()) + all_domains)):
            ds = deed_stats.get(domain, {})
            rj = ds.get("rj", 0)
            price = PRICE_PER_LB.get(domain, 0)

            catalog.append({
                "domain": domain,
                "description": DOMAIN_INFO.get(domain, f"{domain} training data"),
                "total_pairs": pair_counts.get(domain, 0),
                "royal_jelly": rj,
                "avg_score": ds.get("avg_score", 0),
                "price_per_lb": price,
                "in_stock_lbs": rj,
                "status": "available" if rj >= 100 else "coming_soon",
            })

        json_resp(self, {"catalog": catalog, "pricing": PRICE_PER_LB})

    # ── PREVIEW ──
    def handle_preview(self, domain, params):
        limit = min(int(params.get("limit", [5])[0]), 10)
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("""
            SELECT d.id, d.final_score, LEFT(d.judge_a_reasoning, 200), LEFT(d.judge_b_reasoning, 200),
                   p.messages, p.char_count
            FROM deeds d JOIN pairs p ON p.id = d.pair_id
            WHERE d.domain_id = %s AND d.tier = 'royal_jelly'
            ORDER BY d.final_score DESC LIMIT %s
        """, (domain, limit))
        samples = []
        for r in cur.fetchall():
            msgs = r[4] if isinstance(r[4], list) else json.loads(r[4]) if r[4] else []
            samples.append({
                "deed_id": r[0], "score": r[1], "reasoning_a": r[2], "reasoning_b": r[3],
                "system": next((m["content"][:100] for m in msgs if m.get("role") == "system"), ""),
                "user": next((m["content"][:300] for m in msgs if m.get("role") == "user"), ""),
                "assistant": next((m["content"][:300] for m in msgs if m.get("role") == "assistant"), ""),
                "char_count": r[5],
            })
        conn.close()
        json_resp(self, {"domain": domain, "samples": samples})

    # ── CHECKOUT (per-pound pricing) ──
    def handle_checkout(self, body):
        if not STRIPE_KEY:
            json_resp(self, {"error": "Stripe not configured — email build@swarmandbee.ai to order", "contact": "build@swarmandbee.ai"}, 503)
            return

        domain = body.get("domain", "")
        pounds = int(body.get("pounds", 0))
        email = body.get("email", "")

        if not domain or domain not in PRICE_PER_LB:
            json_resp(self, {"error": f"Unknown domain: {domain}"}, 400)
            return
        if pounds < MIN_POUNDS:
            json_resp(self, {"error": f"Minimum order: {MIN_POUNDS} lbs"}, 400)
            return
        if pounds > MAX_POUNDS:
            json_resp(self, {"error": f"Maximum order: {MAX_POUNDS:,} lbs. Contact build@swarmandbee.ai for larger orders."}, 400)
            return
        if not email or "@" not in email:
            json_resp(self, {"error": "Valid email required"}, 400)
            return

        price_per_lb = PRICE_PER_LB[domain]
        total_cents = int(price_per_lb * pounds * 100)
        domain_desc = DOMAIN_INFO.get(domain, domain)

        import stripe
        stripe.api_key = STRIPE_KEY

        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[{
                "price_data": {
                    "currency": "usd",
                    "unit_amount": int(price_per_lb * 100),
                    "product_data": {
                        "name": f"SwarmDeed — {domain.upper()} Class A Weight",
                        "description": f"{pounds:,} lbs Royal Jelly @ ${price_per_lb:.2f}/lb. Dual-scale certified. 5 formats. Deed certs. OM included.",
                    },
                },
                "quantity": pounds,
            }],
            mode="payment",
            success_url=f"{SHOP_URL}?session_id={{CHECKOUT_SESSION_ID}}&status=success",
            cancel_url=f"{SHOP_URL}?status=cancelled",
            customer_email=email,
            metadata={"domain": domain, "pounds": str(pounds), "price_per_lb": str(price_per_lb)},
        )

        log.info("Checkout: %s %d lbs @ $%.2f/lb = $%.2f — %s", domain, pounds, price_per_lb, total_cents/100, email)
        json_resp(self, {"checkout_url": session.url, "session_id": session.id,
                          "domain": domain, "pounds": pounds, "total_cents": total_cents})

    # ── WEBHOOK ──
    def handle_webhook(self, raw_body):
        sig = self.headers.get("Stripe-Signature", "")

        if STRIPE_WEBHOOK_SECRET and sig:
            import stripe
            stripe.api_key = STRIPE_KEY
            try:
                event = stripe.Webhook.construct_event(raw_body, sig, STRIPE_WEBHOOK_SECRET)
            except Exception as e:
                log.error("Webhook signature verification failed: %s", e)
                json_resp(self, {"error": "Invalid signature"}, 400)
                return
        else:
            event = json.loads(raw_body)
            log.warning("Webhook signature not verified (no STRIPE_WEBHOOK_SECRET)")

        event_type = event.get("type", "")
        log.info("Webhook: %s", event_type)

        if event_type in ("checkout.session.completed", "checkout.session.async_payment_succeeded"):
            session = event["data"]["object"]
            email = session.get("customer_email") or session.get("customer_details", {}).get("email", "")
            meta = session.get("metadata", {})
            domain = meta.get("domain", "")
            pounds = int(meta.get("pounds", meta.get("package", "1000").replace("starter", "1000")))
            amount = session.get("amount_total", 0)
            package_key = f"{pounds}lbs"

            if domain and email:
                result = fulfill_order(session["id"], email, domain, package_key, amount, pair_count=pounds)
                if result:
                    json_resp(self, {"fulfilled": True, **result})
                    return

        json_resp(self, {"received": True})

    # ── DOWNLOAD ──
    def handle_download(self, token):
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("""
            SELECT id, domain, package, pair_count, download_expires, download_count
            FROM sales WHERE download_token = %s AND status = 'fulfilled'
        """, (token,))
        row = cur.fetchone()

        if not row:
            conn.close()
            json_resp(self, {"error": "Invalid or expired download link"}, 404)
            return

        order_id, domain, package, pair_count, expires, dl_count = row

        if expires and datetime.now(timezone.utc) > expires:
            conn.close()
            json_resp(self, {"error": "Download link expired. Contact build@swarmandbee.ai"}, 410)
            return

        filepath = DOWNLOAD_DIR / f"{order_id}.zip"
        if not filepath.exists():
            # Rebuild on demand
            log.info("Rebuilding package for %s", order_id)
            zip_bytes, _ = build_package(domain, pair_count, order_id)
            if zip_bytes:
                filepath.write_bytes(zip_bytes)
            else:
                conn.close()
                json_resp(self, {"error": "Package build failed"}, 500)
                return

        # Update download count
        cur.execute("UPDATE sales SET download_count = download_count + 1 WHERE download_token = %s", (token,))
        conn.commit()
        conn.close()

        data = filepath.read_bytes()
        binary_resp(self, data, f"swarmdeed-{domain}-{pair_count}.zip")
        log.info("DOWNLOAD: %s — %s %s (%d bytes, dl #%d)", order_id, domain, package, len(data), dl_count + 1)

    # ── FREE SAMPLE ──
    def handle_free_sample(self, params):
        """Free 100-pair sample. Captures email, sends download, records lead."""
        email = params.get("email", [""])[0].strip()
        domain = params.get("domain", ["medical"])[0]

        if not email or "@" not in email:
            json_resp(self, {"error": "Valid email required for free sample"}, 400)
            return

        # Record lead in sales table
        try:
            conn = get_conn()
            cur = conn.cursor()
            lead_id = f"FREE-{secrets.token_hex(4).upper()}"
            cur.execute("""
                INSERT INTO sales (id, buyer_email, domain, package, pair_count, amount_cents, status, fulfilled_at)
                VALUES (%s, %s, %s, 'free_sample', 100, 0, 'fulfilled', NOW())
                ON CONFLICT DO NOTHING
            """, (lead_id, email, domain))
            conn.commit()
            conn.close()
        except Exception as e:
            log.error("Free sample lead capture failed: %s", e)

        # Send email with download link
        sample_url = f"{SHOP_URL.rstrip('/')}/api/download-free/{domain}"
        if RESEND_KEY:
            try:
                data = json.dumps({
                    "from": "SwarmShop <build@swarmandbee.ai>",
                    "to": [email],
                    "subject": f"Your free {domain} dataset sample — 100 Royal Jelly pairs",
                    "html": f"""<html><body style="font-family:monospace;background:#0a0a0a;color:#e0e0e0;padding:30px;">
<div style="color:#d4a017;font-size:20px;border-bottom:2px solid #d4a017;padding-bottom:10px;">FREE SAMPLE — 100 ROYAL JELLY PAIRS</div>
<div style="background:#111;border:1px solid #333;padding:15px;margin:15px 0;">
<p>Domain: <strong>{domain.upper()}</strong></p>
<p>Pairs: <strong>100 Royal Jelly</strong></p>
<p>Formats: JSONL, CSV, Alpaca + deed certificates</p></div>
<div style="text-align:center;margin:20px 0;">
<a href="{sample_url}" style="color:#d4a017;font-size:16px;font-weight:bold;">DOWNLOAD YOUR FREE SAMPLE</a></div>
<p style="color:#555;font-size:11px;">Want more? Starter: $29 (1,000 pairs) | Professional: $49 (2,500 pairs)</p>
<p style="color:#555;font-size:11px;">swarmandbee.ai/shop</p>
</body></html>""",
                }).encode()
                req = urllib.request.Request("https://api.resend.com/emails", data=data,
                    headers={"Authorization": f"Bearer {RESEND_KEY}", "Content-Type": "application/json"})
                urllib.request.urlopen(req, timeout=10)
            except Exception as e:
                log.error("Free sample email failed: %s", e)

        json_resp(self, {"status": "sent", "email": email, "domain": domain,
                          "download_url": sample_url, "pairs": 100})
        log.info("FREE SAMPLE: %s → %s (%s)", lead_id, email, domain)

    def handle_download_free(self, domain):
        """Serve the pre-built free sample ZIP."""
        filepath = DOWNLOAD_DIR / f"free-{domain}-100.zip"
        if not filepath.exists():
            json_resp(self, {"error": "Sample not available for this domain"}, 404)
            return
        data = filepath.read_bytes()
        binary_resp(self, data, f"swarmdeed-{domain}-free-100.zip")
        log.info("FREE DOWNLOAD: %s (%d bytes)", domain, len(data))

    # ── SALES LEDGER ──
    def handle_sales(self):
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("""
            SELECT id, buyer_email, domain, package, pair_count, amount_cents,
                   status, download_count, created_at
            FROM sales ORDER BY created_at DESC LIMIT 100
        """)
        rows = cur.fetchall()
        conn.close()
        sales = [{"order_id": r[0], "email": r[1], "domain": r[2], "package": r[3],
                   "pairs": r[4], "amount": f"${r[5]/100:.2f}", "status": r[6],
                   "downloads": r[7], "created": r[8]} for r in rows]
        json_resp(self, {"sales": sales, "total": len(sales)})

    def log_message(self, format, *args):
        if args:
            log.debug("%s", args[0])


def serve(port=9092):
    if not DB_URL:
        print("[FATAL] DATABASE_URL not set")
        sys.exit(1)
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT count(*) FROM deeds WHERE tier = 'royal_jelly'")
    rj = cur.fetchone()[0]
    cur.execute("SELECT count(*) FROM sales")
    sales = cur.fetchone()[0]
    conn.close()
    log.info("SwarmShop API starting")
    log.info("  Royal Jelly available: %d", rj)
    log.info("  Sales recorded: %d", sales)
    log.info("  Stripe: %s", "configured" if STRIPE_KEY else "NOT SET")
    log.info("  Webhook secret: %s", "configured" if STRIPE_WEBHOOK_SECRET else "NOT SET")
    log.info("  Resend: %s", "configured" if RESEND_KEY else "NOT SET")
    log.info("  Downloads: %s", DOWNLOAD_DIR)
    log.info("  Port: %d", port)
    HTTPServer(("0.0.0.0", port), ShopHandler).serve_forever()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=9092)
    serve(parser.parse_args().port)
