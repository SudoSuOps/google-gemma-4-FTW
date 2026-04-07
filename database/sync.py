#!/usr/bin/env python3
"""
SwarmGraph Database Sync Engine
================================
Ingests domain datasets into PostgreSQL and aligns with SwarmGraph.
Handles initial bulk load + incremental real-time sync.

Usage:
    python sync.py --domain medical --bulk     # Initial bulk load
    python sync.py --domain all --bulk         # Load all domains
    python sync.py --refresh-views             # Refresh materialized views
    python sync.py --sync-training             # Sync active cook status
"""
import argparse
import json
import hashlib
import time
import os
import sys
from pathlib import Path

try:
    import psycopg2
    from psycopg2.extras import execute_values, Json
except ImportError:
    print("Install psycopg2: pip install psycopg2-binary")
    sys.exit(1)

DB_URL = os.environ.get("DATABASE_URL", "")

DOMAIN_FILES = {
    "medical": "../domains/medical/tribunal_ready/medical_tribunal_ready.jsonl",
    "cre": "../domains/cre/tribunal_ready/cre_tribunal_ready.jsonl",
    "aviation": "../domains/aviation/tribunal_ready/aviation_tribunal_ready.jsonl",
    "grants": "../domains/grants/tribunal_ready/grants_tribunal_ready.jsonl",
}


def get_conn():
    return psycopg2.connect(DB_URL)


def fingerprint(messages):
    content = json.dumps(messages, sort_keys=True, ensure_ascii=True)
    return hashlib.sha256(content.encode()).hexdigest()


def bulk_load_domain(domain, file_path, batch_size=5000):
    """Bulk load a domain's pairs into the database."""
    conn = get_conn()
    cur = conn.cursor()

    abs_path = Path(__file__).parent / file_path
    if not abs_path.exists():
        print(f"[sync] File not found: {abs_path}")
        return 0

    print(f"[sync] Bulk loading {domain} from {abs_path}")

    # Count existing
    cur.execute("SELECT COUNT(*) FROM pairs WHERE domain_id = %s", (domain,))
    existing = cur.fetchone()[0]
    if existing > 0:
        print(f"  Already have {existing:,} pairs for {domain}. Skipping duplicates.")

    loaded = 0
    skipped = 0
    batch = []

    with open(abs_path) as f:
        for line_num, line in enumerate(f, 1):
            if not line.strip():
                continue

            try:
                pair = json.loads(line)
            except json.JSONDecodeError:
                skipped += 1
                continue

            messages = pair.get("messages", [])
            if not messages:
                skipped += 1
                continue

            fp = fingerprint(messages)
            metadata = pair.get("metadata", {})
            char_count = sum(len(m.get("content", "")) for m in messages)

            batch.append((
                fp, domain, Json(messages), char_count, Json(metadata), str(abs_path)
            ))

            if len(batch) >= batch_size:
                inserted = flush_batch(cur, batch)
                loaded += inserted
                skipped += len(batch) - inserted
                batch = []
                if line_num % 50000 == 0:
                    conn.commit()
                    print(f"  {line_num:,} processed, {loaded:,} loaded, {skipped:,} skipped")

    if batch:
        inserted = flush_batch(cur, batch)
        loaded += inserted
        skipped += len(batch) - inserted

    conn.commit()
    cur.close()
    conn.close()

    print(f"[sync] {domain}: {loaded:,} loaded, {skipped:,} skipped")
    return loaded


def flush_batch(cur, batch):
    """Insert a batch of pairs, skipping duplicates."""
    sql = """
        INSERT INTO pairs (fingerprint, domain_id, messages, char_count, metadata, source_file)
        VALUES %s
        ON CONFLICT (fingerprint) DO NOTHING
    """
    try:
        execute_values(cur, sql, batch, page_size=1000)
        return cur.rowcount
    except Exception as e:
        print(f"  Batch error: {e}")
        return 0


def refresh_views():
    """Refresh all materialized views."""
    conn = get_conn()
    cur = conn.cursor()
    print("[sync] Refreshing materialized views...")
    cur.execute("SELECT refresh_all_views()")
    conn.commit()
    cur.close()
    conn.close()
    print("[sync] Views refreshed")


def sync_training():
    """Sync active cook status from training logs."""
    conn = get_conn()
    cur = conn.cursor()

    cook_dirs = [
        ("/home/swarm/swarmgrant-gemma4-31b", "swarmgrant-gemma4-31b"),
    ]

    for cook_dir, writer_id in cook_dirs:
        import glob
        states = sorted(glob.glob(f"{cook_dir}/checkpoint-*/trainer_state.json"))
        if not states:
            continue

        with open(states[-1]) as f:
            state = json.load(f)

        for entry in state.get("log_history", []):
            step = entry.get("step", 0)
            if "loss" in entry:
                cur.execute("""
                    INSERT INTO training_log (writer_id, step, train_loss, learning_rate, epoch)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT DO NOTHING
                """, (writer_id, step, entry.get("loss"), entry.get("learning_rate"), entry.get("epoch")))
            elif "eval_loss" in entry:
                cur.execute("""
                    INSERT INTO training_log (writer_id, step, eval_loss)
                    VALUES (%s, %s, %s)
                    ON CONFLICT DO NOTHING
                """, (writer_id, step, entry.get("eval_loss")))

                # Update writer record
                cur.execute("""
                    UPDATE writers SET eval_loss = %s WHERE id = %s
                """, (entry.get("eval_loss"), writer_id))

    conn.commit()
    cur.close()
    conn.close()
    print("[sync] Training status synced")


def show_stats():
    """Show database statistics."""
    conn = get_conn()
    cur = conn.cursor()

    print(f"\n{'='*60}")
    print(f"  SWARMGRAPH DATABASE STATUS")
    print(f"{'='*60}")

    cur.execute("SELECT COUNT(*) FROM pairs")
    print(f"  Total pairs:  {cur.fetchone()[0]:,}")

    cur.execute("SELECT domain_id, COUNT(*) FROM pairs GROUP BY domain_id ORDER BY COUNT(*) DESC")
    for row in cur.fetchall():
        print(f"    {row[0]:12s}: {row[1]:,}")

    cur.execute("SELECT COUNT(*) FROM deeds")
    print(f"  Total deeds:  {cur.fetchone()[0]:,}")

    cur.execute("SELECT COUNT(*) FROM graph_edges")
    print(f"  Graph edges:  {cur.fetchone()[0]:,}")

    cur.execute("SELECT COUNT(*) FROM audit_log")
    print(f"  Audit entries: {cur.fetchone()[0]:,}")

    print(f"{'='*60}\n")

    cur.close()
    conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SwarmGraph DB Sync")
    parser.add_argument("--domain", help="Domain to load: medical, cre, aviation, grants, all")
    parser.add_argument("--bulk", action="store_true", help="Bulk load mode")
    parser.add_argument("--refresh-views", action="store_true", help="Refresh materialized views")
    parser.add_argument("--sync-training", action="store_true", help="Sync training status")
    parser.add_argument("--stats", action="store_true", help="Show database stats")
    args = parser.parse_args()

    if args.refresh_views:
        refresh_views()
    elif args.sync_training:
        sync_training()
    elif args.stats:
        show_stats()
    elif args.domain and args.bulk:
        if args.domain == "all":
            total = 0
            for domain, path in DOMAIN_FILES.items():
                total += bulk_load_domain(domain, path)
                print()
            print(f"[sync] Total loaded: {total:,}")
        else:
            bulk_load_domain(args.domain, DOMAIN_FILES.get(args.domain, ""))

        refresh_views()
        show_stats()
    else:
        parser.print_help()
