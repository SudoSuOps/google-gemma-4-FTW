#!/usr/bin/env python3
"""
Deed Ledger Exporter — CEO visibility.

Exports the deed ledger to CSV on the NAS so anyone on the network
can open it in Excel/Sheets and see exactly what's been filed.

Run manually or on a cron. Produces two files:
  /mnt/swarm/datasets/deed_ledger.csv    — every deed, every field
  /mnt/swarm/datasets/deed_summary.csv   — one-page summary

Usage:
    DATABASE_URL="postgresql://..." python3 export_ledger.py
"""
import csv
import os
import sys
from datetime import datetime, timezone
from pathlib import Path


def export():
    import psycopg2

    db_url = os.environ.get("DATABASE_URL", "")
    if not db_url:
        print("[FATAL] DATABASE_URL not set")
        sys.exit(1)

    nas = Path(os.environ.get("NAS_DEEDS_PATH", "/mnt/swarm/datasets"))
    conn = psycopg2.connect(db_url)
    cur = conn.cursor()

    # ── FULL LEDGER ──
    cur.execute("""
        SELECT d.id AS deed_id,
               d.domain_id AS domain,
               d.tier,
               d.final_score,
               d.judge_a_id AS judge_a,
               d.judge_a_score,
               d.judge_b_id AS judge_b,
               d.judge_b_score,
               d.max_drift,
               d.validated,
               d.batch_id,
               CASE WHEN d.merkle_root IS NOT NULL THEN 'YES' ELSE 'NO' END AS merkle_filed,
               d.merkle_leaf_idx,
               d.sealed_at,
               LEFT(d.judge_a_reasoning, 200) AS judge_a_reasoning,
               LEFT(d.judge_b_reasoning, 200) AS judge_b_reasoning,
               p.char_count AS pair_chars,
               LEFT(p.fingerprint, 16) AS fingerprint
        FROM deeds d
        JOIN pairs p ON p.id = d.pair_id
        ORDER BY d.sealed_at
    """)
    rows = cur.fetchall()
    cols = [desc[0] for desc in cur.description]

    ledger_path = nas / "deed_ledger.csv"
    with open(ledger_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(cols)
        for row in rows:
            writer.writerow([str(v) if v is not None else "" for v in row])

    # ── SUMMARY ──
    summary_path = nas / "deed_summary.csv"
    with open(summary_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Metric", "Value"])

        cur.execute("SELECT count(*) FROM deeds")
        total_deeds = cur.fetchone()[0]
        w.writerow(["Total Deeds Filed", total_deeds])

        cur.execute("SELECT count(*) FROM batches")
        w.writerow(["Merkle Batches", cur.fetchone()[0]])

        cur.execute("SELECT count(*) FROM deeds WHERE batch_id IS NOT NULL")
        w.writerow(["Deeds in Batches", cur.fetchone()[0]])

        cur.execute("SELECT count(*) FROM deeds WHERE batch_id IS NULL")
        w.writerow(["Deeds Unbatched", cur.fetchone()[0]])

        w.writerow(["", ""])
        w.writerow(["--- TIERS ---", ""])
        cur.execute("SELECT tier, count(*) FROM deeds GROUP BY tier ORDER BY 2 DESC")
        for tier, count in cur.fetchall():
            pct = round(count / max(total_deeds, 1) * 100, 1)
            w.writerow([tier, f"{count} ({pct}%)"])

        w.writerow(["", ""])
        w.writerow(["--- DOMAINS ---", ""])
        cur.execute("SELECT domain_id, count(*) FROM deeds GROUP BY domain_id ORDER BY 2 DESC")
        for domain, count in cur.fetchall():
            w.writerow([domain, count])

        w.writerow(["", ""])
        w.writerow(["--- SCORES ---", ""])
        cur.execute("SELECT avg(final_score), min(final_score), max(final_score) FROM deeds")
        avg_s, min_s, max_s = cur.fetchone()
        w.writerow(["Average Score", f"{avg_s:.4f}" if avg_s else "N/A"])
        w.writerow(["Lowest Score", f"{min_s:.4f}" if min_s else "N/A"])
        w.writerow(["Highest Score", f"{max_s:.4f}" if max_s else "N/A"])

        w.writerow(["", ""])
        w.writerow(["--- PIPELINE ---", ""])
        cur.execute("SELECT count(*) FROM bin WHERE status = 'scored'")
        w.writerow(["Bin: Still Scored (waiting)", cur.fetchone()[0]])
        cur.execute("SELECT count(*) FROM bin WHERE status = 'deeded'")
        w.writerow(["Bin: Deeded (filed)", cur.fetchone()[0]])
        cur.execute("SELECT count(*) FROM bin WHERE status = 'flagged'")
        w.writerow(["Bin: Flagged (review)", cur.fetchone()[0]])

        w.writerow(["", ""])
        w.writerow(["--- FINALITY ---", ""])
        w.writerow(["L1 PostgreSQL", f"{total_deeds} deeds"])
        cur.execute("SELECT count(*) FROM batches")
        w.writerow(["L2 Merkle Batches", cur.fetchone()[0]])
        w.writerow(["L3 IPFS", "NOT YET WIRED"])
        w.writerow(["L4 Hedera", "NOT YET WIRED"])
        w.writerow(["L5 ENS", "swarmgraph.eth (active)"])

        w.writerow(["", ""])
        cur.execute("SELECT min(sealed_at), max(sealed_at) FROM deeds")
        first, last = cur.fetchone()
        w.writerow(["First Deed", str(first)])
        w.writerow(["Latest Deed", str(last)])
        w.writerow(["Exported At", datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")])

    conn.close()
    print(f"[ledger] Exported {len(rows):,} deeds")
    print(f"  Ledger:  {ledger_path}")
    print(f"  Summary: {summary_path}")


if __name__ == "__main__":
    export()
