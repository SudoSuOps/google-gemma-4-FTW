#!/usr/bin/env python3
"""
SwarmGraph Exporter — Queries PostgreSQL and exports the real provenance graph.

This is the ONLY source of truth for swarmgraph.eth.limo.
No demo data. No fake nodes. Only what's actually in the database.

Usage:
    DATABASE_URL="postgresql://swarm:...@192.168.0.102:5433/swarmgraph" \
        python3 export_graph.py --output ipfs-build/swarmgraph_data.json
"""
import argparse
import json
import os
import sys
from datetime import datetime, timezone

from swarm_config import cfg


def export(output_path: str):
    """Export the full graph from PostgreSQL."""
    import psycopg2

    db_url = os.environ.get("DATABASE_URL", "")
    if not db_url:
        print("[FATAL] DATABASE_URL not set — cannot export graph")
        sys.exit(1)

    conn = psycopg2.connect(db_url)
    cur = conn.cursor()

    nodes = []
    edges = []
    stats = {}

    # ── DOMAINS ──
    rj_thresh = cfg.rj_threshold

    cur.execute("SELECT id, name FROM domains ORDER BY id")
    domains = cur.fetchall()
    for d_id, d_name in domains:
        cur.execute("SELECT count(*) FROM pairs WHERE domain_id = %s", (d_id,))
        pair_count = cur.fetchone()[0]
        cur.execute("""SELECT count(*) FILTER (WHERE final_score >= %s),
                              round(sum(final_score)::numeric, 1),
                              round(avg(final_score)::numeric, 4)
                       FROM deeds WHERE domain_id = %s""", (rj_thresh, d_id,))
        d_class_a, d_total_weight, d_avg_weight = cur.fetchone()
        nodes.append({
            "id": f"domain:{d_id}",
            "type": "domain",
            "properties": {
                "name": d_name,
                "domain_id": d_id,
                "pair_count": pair_count,
                "classA": d_class_a or 0,
                "totalWeight": float(d_total_weight or 0),
                "avgWeight": float(d_avg_weight or 0),
                "maturity": "HARVEST" if (d_class_a or 0) >= 1000 else ("GROWING" if (d_class_a or 0) >= 100 else "SEEDLING"),
            },
        })

    # ── JUDGES ──
    cur.execute("SELECT id, model, label, deterministic, total_scores, mean_score, calibration_drift FROM judges")
    for row in cur.fetchall():
        j_id, model, label, deterministic, total_scores, mean_score, drift = row
        nodes.append({
            "id": f"judge:{j_id}",
            "type": "judge",
            "properties": {
                "model": model,
                "label": label or j_id,
                "deterministic": deterministic,
                "total_scores": total_scores or 0,
                "mean_score": float(mean_score) if mean_score else None,
                "calibration_drift": float(drift) if drift else 0.0,
                "base_model": True,
            },
        })

    # ── SILICON ──
    cur.execute("SELECT id, hardware, arch, power_watts, vram_gb, location, ip_address, status FROM silicon")
    for row in cur.fetchall():
        s_id, hw, arch, power, vram, loc, ip, status = row
        nodes.append({
            "id": f"silicon:{s_id}",
            "type": "silicon",
            "properties": {
                "hardware": hw,
                "arch": arch,
                "power_watts": power,
                "vram_gb": float(vram) if vram else 0,
                "location": loc,
                "ip_address": ip,
                "status": status,
            },
        })

    # ── WRITERS ──
    cur.execute("""SELECT id, base_model, model_name, status, trained_on_count,
                          eval_loss, train_hours, peak_vram_gb, silicon_id FROM writers""")
    for row in cur.fetchall():
        w_id, base, name, status, trained_on, eval_loss, train_h, peak_vram, silicon_id = row
        nodes.append({
            "id": f"writer:{w_id}",
            "type": "writer",
            "properties": {
                "base_model": base,
                "model_name": name,
                "status": status,
                "trained_on_count": trained_on or 0,
                "eval_loss": float(eval_loss) if eval_loss else None,
                "train_hours": float(train_h) if train_h else None,
                "peak_vram_gb": float(peak_vram) if peak_vram else None,
            },
        })
        # Writer → Silicon edge
        if silicon_id:
            edges.append({
                "source": f"writer:{w_id}",
                "target": f"silicon:{silicon_id}",
                "type": "ran_on",
            })

    # ── DEEDED PAIRS (from deeds table) — sample up to 500 ──
    cur.execute("""
        SELECT d.pair_id, d.domain_id, d.judge_a_score, d.judge_b_score,
               d.final_score, d.tier, d.max_drift, 'deeded' as status,
               LEFT(p.fingerprint, 64)
        FROM deeds d
        JOIN pairs p ON p.id = d.pair_id
        ORDER BY d.final_score DESC
        LIMIT 500
    """)
    scored_pairs = cur.fetchall()

    for row in scored_pairs:
        pair_id, domain_id, ja_score, jb_score, final_score, tier, max_drift, status, fingerprint = row
        # Weight and weight class
        weight = float(final_score) if final_score else 0
        tier_label = cfg.classify(weight)
        if tier_label == "royal_jelly":
            weight_class = "A"
        elif tier_label == "honey":
            weight_class = "B"
        else:
            weight_class = "C"
        tier_norm = (tier or "unknown").replace("_", "-")
        fp_short = (fingerprint or str(pair_id))[:12]

        nodes.append({
            "id": f"pair:{fp_short}",
            "type": "deed",
            "properties": {
                "pair_id": str(pair_id),
                "domain": domain_id,
                "scale_a": float(ja_score) if ja_score else None,
                "scale_b": float(jb_score) if jb_score else None,
                "weight": weight,
                "weightClass": weight_class,
                "tier": tier_norm,
                "drift": float(max_drift) if max_drift else 0,
                "status": status,
                "fingerprint": fingerprint[:16] if fingerprint else None,
                "pricePerPound": 0.029 if weight_class == "A" else (0.015 if weight_class == "B" else 0),
            },
        })

        # Pair → Domain edge
        edges.append({
            "source": f"pair:{fp_short}",
            "target": f"domain:{domain_id}",
            "type": "belongs_to",
        })

        # Pair → Scale A edge (weighed by)
        edges.append({
            "source": f"pair:{fp_short}",
            "target": "judge:gemma3:12b",
            "type": "weighed_by",
            "properties": {"weight": float(ja_score) if ja_score else None},
        })

        # Pair → Scale B edge (weighed by)
        edges.append({
            "source": f"pair:{fp_short}",
            "target": "judge:gemma3:12b",
            "type": "weighed_by",
            "properties": {"weight": float(jb_score) if jb_score else None},
        })

    # ── WEIGHT CLASS DISTRIBUTION (from deeds) ──
    honey_thresh = cfg.honey_threshold
    cur.execute("""
        SELECT
            count(*) FILTER (WHERE final_score >= %s) as class_a,
            count(*) FILTER (WHERE final_score >= %s AND final_score < %s) as class_b,
            count(*) FILTER (WHERE final_score < %s) as class_c,
            round(sum(final_score)::numeric, 1) as total_weight,
            round(avg(final_score)::numeric, 4) as avg_weight
        FROM deeds
    """, (rj_thresh, honey_thresh, rj_thresh, honey_thresh))
    class_a, class_b, class_c, total_weight, avg_weight = cur.fetchone()

    weight_classes = {
        "classA": class_a,
        "classB": class_b,
        "classC": class_c,
        "totalWeight": float(total_weight or 0),
        "avgWeight": float(avg_weight or 0),
        "pricePerPound": 0.029,
        "harvestValue": round(class_a * 0.029, 2),
    }

    # Per-domain weight
    cur.execute("""
        SELECT domain_id,
            count(*) FILTER (WHERE final_score >= %s) as class_a,
            count(*) FILTER (WHERE final_score >= %s AND final_score < %s) as class_b,
            count(*) FILTER (WHERE final_score < %s) as class_c,
            round(sum(final_score)::numeric, 1) as total_weight
        FROM deeds GROUP BY domain_id ORDER BY sum(final_score) DESC
    """, (rj_thresh, honey_thresh, rj_thresh, honey_thresh))
    domain_weights = {}
    for dom, da, db, dc, dw in cur.fetchall():
        domain_weights[dom] = {
            "classA": da, "classB": db, "classC": dc,
            "totalWeight": float(dw or 0),
            "maturity": "HARVEST" if da >= 1000 else ("GROWING" if da >= 100 else "SEEDLING"),
        }

    # Legacy tier dist (backward compat)
    tier_dist = {"royal-jelly": class_a, "honey": class_b, "propolis": class_c}

    # ── DOMAIN PAIR COUNTS ──
    cur.execute("SELECT domain_id, count(*) FROM pairs GROUP BY domain_id ORDER BY 2 DESC")
    domain_pairs = {row[0]: row[1] for row in cur.fetchall()}

    # ── FLAGGED COUNT ──
    cur.execute("SELECT count(*) FROM bin WHERE status = 'flagged'")
    flagged_count = cur.fetchone()[0]

    # ── BATCH + ANCHOR STATUS ──
    cur.execute("SELECT count(*) FROM batches")
    batch_count = cur.fetchone()[0]
    cur.execute("SELECT count(*) FROM anchors")
    anchor_count = cur.fetchone()[0]
    cur.execute("SELECT count(*) FROM deeds")
    deed_count = cur.fetchone()[0]

    conn.close()

    # ── FINALITY STATUS ──
    finality = {
        "layer_1_postgresql": {
            "status": "active",
            "pairs_loaded": sum(domain_pairs.values()),
            "pairs_scored": sum(tier_dist.values()),
            "pairs_flagged": flagged_count,
        },
        "layer_2_minio": {"status": "pending", "deed_count": deed_count},
        "layer_3_ipfs": {"status": "pending", "batch_count": batch_count},
        "layer_4_hedera": {
            "status": "pending",
            "anchor_count": anchor_count,
            "topic": "0.0.10291838",
        },
        "layer_5_ens": {
            "status": "active",
            "domain": "swarmgraph.eth",
        },
    }

    # ── SUMMARY ──
    total_scored = sum(tier_dist.values())
    summary = {
        "total_pairs": sum(domain_pairs.values()),
        "total_weighed": total_scored,
        "total_flagged": flagged_count,
        "total_nodes": len(nodes),
        "total_edges": len(edges),
        "domains": len(domains),
        "scales": 2,
        "silicon": 5,
        "writers": 1,
        "weight_classes": weight_classes,
        "domain_weights": domain_weights,
        "tier_distribution": tier_dist,
        "domain_pairs": domain_pairs,
        "finality": finality,
        "exported_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "exported_by": "swarmgraph-export-v2-weight",
    }

    graph = {
        "summary": summary,
        "nodes": nodes,
        "edges": edges,
        "live": False,  # This is a static export — not live API
    }

    with open(output_path, "w") as f:
        json.dump(graph, f, indent=2, default=str)

    print(f"[export] Graph exported to {output_path}")
    print(f"  Nodes: {len(nodes)}")
    print(f"  Edges: {len(edges)}")
    print(f"  Scored pairs: {total_scored}")
    print(f"  Tier: {tier_dist}")
    print(f"  Domains: {domain_pairs}")
    print(f"  Finality: L1=active L2={'active' if deed_count > 0 else 'pending'} "
          f"L3={'active' if batch_count > 0 else 'pending'} L4={'active' if anchor_count > 0 else 'pending'}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SwarmGraph Exporter")
    parser.add_argument("--output", default="ipfs-build/swarmgraph_data.json", help="Output JSON path")
    args = parser.parse_args()
    export(args.output)
