#!/usr/bin/env python3
"""
Swarm Watchdog — Always-On Fleet Health Monitor
================================================
Runs on zima-edge (.230) as a systemd service.
Checks every system every 5 minutes.
Writes status JSON to NAS for the /status page.
Sends email alert on critical failures via Resend.

Checks:
  - All swarmandbee.ai routes (deed, chain, shop, graph)
  - PostgreSQL deed count (is the recorder filing?)
  - Deed recorder service (is it alive?)
  - NAS mount (is shared storage accessible?)
  - GPU training (is the cook still running?)
  - Fleet nodes (edge, whale, jetson — SSH ping)

Usage:
    DATABASE_URL="postgresql://..." python3 swarm_watchdog.py
"""
import json
import logging
import os
import signal
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [watchdog] %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("watchdog")

DB_URL = os.environ.get("DATABASE_URL", "")
NAS_STATUS = Path(os.environ.get("NAS_STATUS_PATH", "/mnt/swarm/status"))
RESEND_KEY = os.environ.get("RESEND_API_KEY", "")
ALERT_EMAIL = os.environ.get("ALERT_EMAIL", "build@swarmandbee.ai")
CHECK_INTERVAL = int(os.environ.get("CHECK_INTERVAL", "300"))  # 5 minutes

SITE_BASE = "https://swarmandbee.ai"

_running = True
def _shutdown(sig, frame):
    global _running
    log.info("Shutdown signal received")
    _running = False
signal.signal(signal.SIGTERM, _shutdown)
signal.signal(signal.SIGINT, _shutdown)


def check_url(url, timeout=10):
    """Check if a URL returns 200. Returns (ok, latency_ms, detail)."""
    try:
        start = time.time()
        req = urllib.request.Request(url, headers={"User-Agent": "swarm-watchdog/1.0"})
        resp = urllib.request.urlopen(req, timeout=timeout)
        latency = int((time.time() - start) * 1000)
        body = resp.read(1024).decode("utf-8", errors="replace")
        return True, latency, body[:200]
    except Exception as e:
        return False, 0, str(e)[:200]


def check_db():
    """Check PostgreSQL connectivity and deed count."""
    try:
        import psycopg2
        start = time.time()
        conn = psycopg2.connect(DB_URL, connect_timeout=5)
        cur = conn.cursor()
        cur.execute("SELECT count(*) FROM deeds")
        deeds = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM bin WHERE status = 'scored'")
        remaining = cur.fetchone()[0]
        cur.execute("SELECT max(sealed_at) FROM deeds")
        last_deed = cur.fetchone()[0]
        latency = int((time.time() - start) * 1000)
        conn.close()
        return True, latency, {"deeds": deeds, "remaining": remaining, "last_deed": str(last_deed)}
    except Exception as e:
        return False, 0, {"error": str(e)[:200]}


def check_service(name):
    """Check if a systemd service is active."""
    try:
        r = subprocess.run(["systemctl", "is-active", name], capture_output=True, text=True, timeout=5)
        active = r.stdout.strip() == "active"
        return active, 0, r.stdout.strip()
    except Exception as e:
        return False, 0, str(e)


def check_ssh(host, timeout=5):
    """Check if a host is reachable via SSH."""
    try:
        start = time.time()
        r = subprocess.run(
            ["ssh", "-o", "BatchMode=yes", "-o", f"ConnectTimeout={timeout}", host, "echo ok"],
            capture_output=True, text=True, timeout=timeout + 2,
        )
        latency = int((time.time() - start) * 1000)
        return r.returncode == 0, latency, r.stdout.strip() or r.stderr.strip()[:100]
    except Exception as e:
        return False, 0, str(e)[:100]


def check_gpu(host="swarm@192.168.0.91"):
    """Check GPU status on swarmrails via SSH."""
    try:
        r = subprocess.run(
            ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=5", host,
             "nvidia-smi --query-gpu=index,temperature.gpu,power.draw,utilization.gpu,memory.used --format=csv,noheader,nounits 2>/dev/null; "
             "ps -p $(pgrep -f 'train_swarmgrant' | head -1) --no-headers -o pid,etime 2>/dev/null || echo 'NO_TRAINING'"],
            capture_output=True, text=True, timeout=10,
        )
        lines = r.stdout.strip().split("\n")
        gpus = []
        training = None
        for line in lines:
            if "NO_TRAINING" in line:
                training = "not running"
            elif "," in line and len(line.split(",")) >= 4:
                parts = [p.strip() for p in line.split(",")]
                gpus.append({"gpu": parts[0], "temp": parts[1], "power": parts[2], "util": parts[3], "vram": parts[4] if len(parts) > 4 else "?"})
            elif line.strip() and "," not in line:
                training = line.strip()
        return True, 0, {"gpus": gpus, "training": training}
    except Exception as e:
        return False, 0, {"error": str(e)[:100]}


def send_alert(subject, body):
    """Send alert email via Resend."""
    if not RESEND_KEY:
        log.warning("No RESEND_API_KEY — alert not sent: %s", subject)
        return False
    try:
        data = json.dumps({
            "from": "SwarmWatchdog <build@swarmandbee.ai>",
            "to": [ALERT_EMAIL],
            "subject": f"[SWARM ALERT] {subject}",
            "text": body,
        }).encode()
        req = urllib.request.Request(
            "https://api.resend.com/emails",
            data=data,
            headers={"Authorization": f"Bearer {RESEND_KEY}", "Content-Type": "application/json"},
        )
        urllib.request.urlopen(req, timeout=10)
        log.info("Alert sent: %s", subject)
        return True
    except Exception as e:
        log.error("Alert send failed: %s", e)
        return False


def run_checks():
    """Run all checks and return status dict."""
    now = datetime.now(timezone.utc)
    checks = {}

    # ── Web routes ──
    routes = {
        "site_main": "/",
        "deed_ui": "/deed/",
        "deed_api": "/deed/api/stats",
        "chain_ui": "/chain/",
        "chain_api": "/chain/api/health",
        "shop_ui": "/shop/",
        "shop_api": "/shop/api/catalog",
        "graph_ui": "/graph/",
    }
    for name, path in routes.items():
        ok, ms, detail = check_url(f"{SITE_BASE}{path}")
        checks[name] = {"ok": ok, "latency_ms": ms, "detail": detail[:100] if isinstance(detail, str) else ""}

    # ── Database ──
    ok, ms, detail = check_db()
    checks["postgresql"] = {"ok": ok, "latency_ms": ms, **detail}

    # ── Local services (on this edge box) ──
    ok, _, detail = check_service("deed-recorder")
    checks["deed_recorder"] = {"ok": ok, "detail": detail}

    # ── NAS mount ──
    nas_ok = NAS_STATUS.parent.exists()
    checks["nas_mount"] = {"ok": nas_ok, "detail": "mounted" if nas_ok else "NOT MOUNTED"}

    # ── Fleet SSH ──
    for name, host in [("swarmrails", "swarm@192.168.0.91"), ("whale", "swarm@192.168.0.99")]:
        ok, ms, detail = check_ssh(host)
        checks[name] = {"ok": ok, "latency_ms": ms, "detail": detail}

    # ── GPU / Training ──
    ok, _, detail = check_gpu()
    checks["gpu_training"] = {"ok": ok, **detail}

    # ── Summary ──
    total = len(checks)
    passed = sum(1 for c in checks.values() if c.get("ok"))
    failed = [k for k, v in checks.items() if not v.get("ok")]

    status = {
        "timestamp": now.isoformat(),
        "checks": checks,
        "summary": {
            "total": total,
            "passed": passed,
            "failed": len(failed),
            "failed_names": failed,
            "status": "ALL SYSTEMS GO" if not failed else f"{len(failed)} FAILURES",
        },
    }
    return status


def run():
    log.info("═══ SWARM WATCHDOG STARTING ═══")
    log.info("  Check interval: %ds", CHECK_INTERVAL)
    log.info("  Status output:  %s", NAS_STATUS)
    log.info("  Alert email:    %s", ALERT_EMAIL)

    NAS_STATUS.mkdir(parents=True, exist_ok=True)
    prev_failed = set()

    while _running:
        try:
            status = run_checks()
            s = status["summary"]

            # Write to NAS
            status_file = NAS_STATUS / "watchdog.json"
            with open(status_file, "w") as f:
                json.dump(status, f, indent=2, default=str)

            # Also write a simple one-liner
            oneliner = NAS_STATUS / "status.txt"
            now = status["timestamp"][:19]
            with open(oneliner, "w") as f:
                f.write(f"{now} | {s['status']} | {s['passed']}/{s['total']} checks pass\n")
                if s["failed_names"]:
                    f.write(f"FAILED: {', '.join(s['failed_names'])}\n")

            # Push to Zima Lite for web serving
            try:
                subprocess.run(
                    ["scp", "-o", "BatchMode=yes", "-o", "ConnectTimeout=5",
                     str(status_file), "bee@192.168.0.173:/home/bee/swarmandbee/html/status/watchdog.json"],
                    capture_output=True, timeout=10,
                )
            except Exception:
                pass  # Non-critical — NAS copy is the primary

            # Log
            if s["failed"]:
                log.warning("CHECK: %d/%d pass — FAILURES: %s", s["passed"], s["total"], ", ".join(s["failed_names"]))
            else:
                log.info("CHECK: %d/%d pass — ALL SYSTEMS GO", s["passed"], s["total"])

            # Alert on NEW failures
            current_failed = set(s["failed_names"])
            new_failures = current_failed - prev_failed
            if new_failures:
                alert_body = f"New failures detected at {now}:\n\n"
                for name in new_failures:
                    c = status["checks"][name]
                    alert_body += f"  FAIL: {name} — {c.get('detail', 'unknown')}\n"
                alert_body += f"\nTotal: {s['passed']}/{s['total']} passing\nDashboard: {SITE_BASE}/status/"
                send_alert(f"{len(new_failures)} new failure(s): {', '.join(new_failures)}", alert_body)

            # Alert on recovery
            recovered = prev_failed - current_failed
            if recovered:
                log.info("RECOVERED: %s", ", ".join(recovered))

            prev_failed = current_failed

        except Exception as e:
            log.error("Watchdog loop error: %s", e, exc_info=True)

        time.sleep(CHECK_INTERVAL)

    log.info("═══ SWARM WATCHDOG STOPPED ═══")


if __name__ == "__main__":
    run()
