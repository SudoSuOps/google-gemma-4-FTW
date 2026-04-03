#!/usr/bin/env python3
"""
SwarmGraph CLI
==============
Query and manage the context graph from the command line.

Usage:
    python -m swarmgraph.cli summary
    python -m swarmgraph.cli ingest --deeds domains/medical/scored/scored.jsonl --domain medical
    python -m swarmgraph.cli provenance --node deed:SB-2026-0402-00001
    python -m swarmgraph.cli impact --node judge:gemma-4-e2b
    python -m swarmgraph.cli domain-stats --domain medical
    python -m swarmgraph.cli judge-calibration --judge gemma-4-e2b
    python -m swarmgraph.cli model-provenance --writer swarmgrant-gemma4-31b
    python -m swarmgraph.cli export --output swarmgraph_export.json
    python -m swarmgraph.cli register-silicon
"""
import argparse
import json
import sys
from pathlib import Path

from .graph import SwarmGraph
from .nodes import NodeType

GRAPH_STATE = Path("swarmgraph_state.json")


def load_graph() -> SwarmGraph:
    """Load graph from persisted state or create new."""
    g = SwarmGraph(name="swarm-and-bee")

    if GRAPH_STATE.exists():
        with open(GRAPH_STATE) as f:
            state = json.load(f)
        # Rebuild from state
        from .nodes import Node, Edge, EdgeType
        for nd in state.get("nodes", []):
            g.add_node(Node(
                id=nd["id"],
                type=NodeType(nd["type"]),
                properties=nd.get("properties", {}),
                created_at=nd.get("created_at"),
            ))
        for ed in state.get("edges", []):
            g.add_edge(Edge(
                source_id=ed["source"],
                target_id=ed["target"],
                type=EdgeType(ed["type"]),
                properties=ed.get("properties", {}),
            ))
        print(f"[swarmgraph] Loaded: {len(g.nodes):,} nodes, {len(g.edges):,} edges")
    else:
        print(f"[swarmgraph] New graph initialized")

    return g


def save_graph(g: SwarmGraph):
    """Persist graph state."""
    g.export_json(str(GRAPH_STATE))


def cmd_summary(g, args):
    s = g.summary()
    print(f"\n{'='*60}")
    print(f"  SWARMGRAPH — {s['name']}")
    print(f"{'='*60}")
    print(f"  Nodes: {s['total_nodes']:,}")
    print(f"  Edges: {s['total_edges']:,}")
    print(f"\n  Node Types:")
    for t, c in sorted(s["node_types"].items(), key=lambda x: -x[1]):
        print(f"    {t:15s}: {c:,}")
    if s["tier_distribution"]:
        print(f"\n  Tier Distribution:")
        for t, c in sorted(s["tier_distribution"].items()):
            print(f"    {t:15s}: {c:,}")
    print(f"{'='*60}\n")


def cmd_ingest(g, args):
    count = g.ingest_deeds(args.deeds, args.domain)
    save_graph(g)
    print(f"Ingested {count:,} deeds. Graph saved.")


def cmd_provenance(g, args):
    trace = g.trace_provenance(args.node)
    print(json.dumps(trace, indent=2))


def cmd_impact(g, args):
    trace = g.trace_impact(args.node)
    print(json.dumps(trace, indent=2))


def cmd_domain_stats(g, args):
    stats = g.query_domain_stats(args.domain)
    print(json.dumps(stats, indent=2))


def cmd_judge_calibration(g, args):
    stats = g.query_judge_calibration(f"judge:{args.judge}")
    print(json.dumps(stats, indent=2))


def cmd_model_provenance(g, args):
    prov = g.query_model_provenance(f"writer:{args.writer}")
    print(json.dumps(prov, indent=2))


def cmd_export(g, args):
    g.export_json(args.output)


def cmd_register_silicon(g, args):
    # Register the Swarm & Bee hardware fleet
    fleet = [
        ("swarmrails-gpu0", "NVIDIA RTX PRO 6000 Blackwell 96GB", "Blackwell", 300, "datacenter"),
        ("swarmrails-gpu1", "NVIDIA RTX PRO 6000 Blackwell 96GB", "Blackwell", 300, "datacenter"),
        ("whale-gpu0", "NVIDIA RTX 3090 24GB", "Ampere", 350, "datacenter"),
        ("jetson-sigedge", "NVIDIA Jetson Orin Nano 8GB", "Ampere", 6, "edge"),
        ("zima-t1000", "NVIDIA T1000 4GB", "Turing", 50, "edge"),
        ("swarmrails-cpu", "Intel Xeon w9-3475X (AMX INT8/BF16)", "Sapphire Rapids", 250, "datacenter"),
    ]
    for sid, hw, arch, watts, loc in fleet:
        g.register_silicon(sid, hw, arch, watts, loc)
        print(f"  Registered: {sid} ({hw})")
    save_graph(g)


def main():
    parser = argparse.ArgumentParser(description="SwarmGraph CLI")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("summary")

    p_ingest = sub.add_parser("ingest")
    p_ingest.add_argument("--deeds", required=True)
    p_ingest.add_argument("--domain", required=True)

    p_prov = sub.add_parser("provenance")
    p_prov.add_argument("--node", required=True)

    p_impact = sub.add_parser("impact")
    p_impact.add_argument("--node", required=True)

    p_ds = sub.add_parser("domain-stats")
    p_ds.add_argument("--domain", required=True)

    p_jc = sub.add_parser("judge-calibration")
    p_jc.add_argument("--judge", required=True)

    p_mp = sub.add_parser("model-provenance")
    p_mp.add_argument("--writer", required=True)

    p_exp = sub.add_parser("export")
    p_exp.add_argument("--output", default="swarmgraph_export.json")

    sub.add_parser("register-silicon")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    g = load_graph()

    commands = {
        "summary": cmd_summary,
        "ingest": cmd_ingest,
        "provenance": cmd_provenance,
        "impact": cmd_impact,
        "domain-stats": cmd_domain_stats,
        "judge-calibration": cmd_judge_calibration,
        "model-provenance": cmd_model_provenance,
        "export": cmd_export,
        "register-silicon": cmd_register_silicon,
    }

    commands[args.command](g, args)


if __name__ == "__main__":
    main()
