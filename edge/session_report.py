#!/usr/bin/env python3
"""
Tribunal Session Report — Auto-generated daily summary.
Like Karpathy's autoresearch session reports, but for data quality.

Generates a report of what the tribunal scored in the last N hours.
Saves to NAS + pushes to blog via Zima Lite.

Usage:
    DATABASE_URL="postgresql://..." python3 session_report.py --hours 24
"""
import json
import os
import sys
from datetime import datetime, timezone, timedelta

from swarm_config import cfg


def generate_report(hours=24):
    import psycopg2

    db_url = os.environ.get("DATABASE_URL", "")
    if not db_url:
        print("[FATAL] DATABASE_URL not set")
        sys.exit(1)

    conn = psycopg2.connect(db_url)
    cur = conn.cursor()
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

    # Total deeds in period
    cur.execute("SELECT count(*) FROM deeds WHERE sealed_at >= %s", (cutoff,))
    total = cur.fetchone()[0]

    # By tier
    cur.execute("""
        SELECT tier, count(*) FROM deeds
        WHERE sealed_at >= %s GROUP BY tier ORDER BY 2 DESC
    """, (cutoff,))
    tiers = dict(cur.fetchall())

    # By domain
    cur.execute("""
        SELECT domain_id, count(*), round(avg(final_score)::numeric, 4),
               count(*) FILTER (WHERE tier = 'royal_jelly')
        FROM deeds WHERE sealed_at >= %s
        GROUP BY domain_id ORDER BY 2 DESC
    """, (cutoff,))
    domains = [{"domain": r[0], "total": r[1], "avg": float(r[2] or 0), "rj": r[3]}
               for r in cur.fetchall()]

    # Flagged
    cur.execute("SELECT count(*) FROM bin WHERE status = 'flagged' AND scored_at >= %s", (cutoff,))
    flagged = cur.fetchone()[0]

    # Score distribution (thresholds from centralized config)
    rj_t = cfg.rj_threshold
    h_t = cfg.honey_threshold
    cur.execute("""
        SELECT CASE
            WHEN final_score >= %s THEN %s
            WHEN final_score >= %s THEN %s
            WHEN final_score >= %s THEN %s
            WHEN final_score >= %s THEN %s
            ELSE %s
        END, count(*)
        FROM deeds WHERE sealed_at >= %s
        GROUP BY 1 ORDER BY 1
    """, (
        rj_t + 0.05, f"{rj_t + 0.05:.2f}+",
        rj_t,        f"{rj_t:.2f}-{rj_t + 0.04:.2f}",
        h_t + 0.10,  f"{h_t + 0.10:.2f}-{rj_t - 0.01:.2f}",
        h_t,         f"{h_t:.2f}-{h_t + 0.09:.2f}",
                     f"below {h_t:.2f}",
        cutoff,
    ))
    score_dist = dict(cur.fetchall())

    # Top scoring pairs (compound findings)
    cur.execute("""
        SELECT d.id, d.domain_id, d.final_score, d.judge_a_score, d.judge_b_score,
               LEFT(d.judge_a_reasoning, 100)
        FROM deeds d WHERE d.sealed_at >= %s
        ORDER BY d.final_score DESC LIMIT 5
    """, (cutoff,))
    top_pairs = [{"deed_id": r[0], "domain": r[1], "score": r[2],
                  "a": r[3], "b": r[4], "reason": r[5]} for r in cur.fetchall()]

    # Lowest scoring (dead ends / propolis findings)
    cur.execute("""
        SELECT d.id, d.domain_id, d.final_score, d.judge_a_score, d.judge_b_score,
               LEFT(d.judge_a_reasoning, 100)
        FROM deeds d WHERE d.sealed_at >= %s AND d.tier = 'propolis'
        ORDER BY d.final_score ASC LIMIT 5
    """, (cutoff,))
    dead_ends = [{"deed_id": r[0], "domain": r[1], "score": r[2],
                  "a": r[3], "b": r[4], "reason": r[5]} for r in cur.fetchall()]

    # Judge agreement in period
    cur.execute("""
        SELECT round(avg(abs(judge_a_score - judge_b_score))::numeric, 4),
               count(*) FILTER (WHERE abs(judge_a_score - judge_b_score) > 0.20)
        FROM deeds WHERE sealed_at >= %s
    """, (cutoff,))
    agree = cur.fetchone()

    # Hourly throughput
    cur.execute("""
        SELECT date_trunc('hour', sealed_at), count(*)
        FROM deeds WHERE sealed_at >= %s
        GROUP BY 1 ORDER BY 1
    """, (cutoff,))
    throughput = [{"hour": str(h), "count": c} for h, c in cur.fetchall()]

    # All-time totals
    cur.execute("SELECT count(*) FROM deeds")
    all_time_deeds = cur.fetchone()[0]
    cur.execute("SELECT count(*) FROM batches")
    all_time_batches = cur.fetchone()[0]

    conn.close()

    rj = tiers.get("royal_jelly", 0)
    honey = tiers.get("honey", 0)
    propolis = tiers.get("propolis", 0)
    rj_rate = round(rj / max(total, 1) * 100, 1)
    avg_rate = round(total / max(hours, 1), 1)

    report = {
        "title": f"Tribunal Session Report — {hours}h",
        "period_hours": hours,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "total_scored": total,
            "rate_per_hour": avg_rate,
            "royal_jelly": rj,
            "honey": honey,
            "propolis": propolis,
            "flagged": flagged,
            "rj_rate_pct": rj_rate,
        },
        "domains": domains,
        "score_distribution": score_dist,
        "judge_agreement": {
            "avg_gap": float(agree[0] or 0),
            "high_disagreement": agree[1],
        },
        "top_pairs": top_pairs,
        "dead_ends": dead_ends,
        "throughput": throughput,
        "all_time": {
            "total_deeds": all_time_deeds,
            "total_batches": all_time_batches,
        },
    }

    # Print human-readable
    print(f"═══ TRIBUNAL SESSION REPORT — {hours}h ═══")
    print(f"Generated: {report['generated_at'][:19]}")
    print()
    print(f"  Scored:     {total:,}")
    print(f"  Rate:       {avg_rate}/hr")
    print(f"  Royal Jelly: {rj:,} ({rj_rate}%)")
    print(f"  Honey:      {honey:,}")
    print(f"  Propolis:   {propolis:,}")
    print(f"  Flagged:    {flagged}")
    print()
    print("  DOMAINS:")
    for d in domains:
        print(f"    {d['domain']:15s} {d['total']:>5,} scored | avg {d['avg']} | RJ: {d['rj']:,}")
    print()
    print("  TOP PAIRS (compound findings):")
    for p in top_pairs:
        print(f"    {p['deed_id']} {p['score']:.3f} A:{p['a']:.2f} B:{p['b']:.2f} {p['domain']}")
    print()
    print("  DEAD ENDS (propolis — failure intelligence):")
    for p in dead_ends:
        print(f"    {p['deed_id']} {p['score']:.3f} {p['domain']} — {(p['reason'] or '')[:60]}")
    print()
    print(f"  ALL TIME: {all_time_deeds:,} deeds | {all_time_batches} batches")

    return report


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--hours", type=int, default=24)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    report = generate_report(args.hours)
    if args.json:
        print(json.dumps(report, indent=2, default=str))
