"""
SwarmGraph Engine
==================
The context graph for AI training data.
Append-only. Deterministic. Lossless. Anchored. Traversable.

Every node is a decision. Every edge is provenance.
Pull any node — the full decision trace unwinds.
"""
import json
import time
import hashlib
from collections import defaultdict
from pathlib import Path
from typing import Optional

from .nodes import Node, Edge, NodeType, EdgeType


class SwarmGraph:
    """
    A directed context graph mapping the complete decision history
    of AI training data from raw pair to deployed model.
    """

    def __init__(self, name="swarmgraph"):
        self.name = name
        self.nodes: dict[str, Node] = {}
        self.edges: list[Edge] = []
        self._outgoing: dict[str, list[Edge]] = defaultdict(list)  # node_id → edges from
        self._incoming: dict[str, list[Edge]] = defaultdict(list)  # node_id → edges to
        self._type_index: dict[NodeType, list[str]] = defaultdict(list)
        self.created_at = time.strftime("%Y-%m-%dT%H:%M:%SZ")
        self.stats = {"nodes_added": 0, "edges_added": 0, "deeds_ingested": 0}

    # ─── NODE OPERATIONS ───

    def add_node(self, node: Node) -> Node:
        """Add a node to the graph. Append-only — never overwrites."""
        if node.id not in self.nodes:
            if not node.created_at:
                node.created_at = time.strftime("%Y-%m-%dT%H:%M:%SZ")
            self.nodes[node.id] = node
            self._type_index[node.type].append(node.id)
            self.stats["nodes_added"] += 1
        return self.nodes[node.id]

    def get_node(self, node_id: str) -> Optional[Node]:
        return self.nodes.get(node_id)

    def nodes_by_type(self, node_type: NodeType) -> list[Node]:
        return [self.nodes[nid] for nid in self._type_index.get(node_type, []) if nid in self.nodes]

    # ─── EDGE OPERATIONS ───

    def add_edge(self, edge: Edge) -> Edge:
        """Add a directed edge. Append-only."""
        self.edges.append(edge)
        self._outgoing[edge.source_id].append(edge)
        self._incoming[edge.target_id].append(edge)
        self.stats["edges_added"] += 1
        return edge

    def connect(self, source_id: str, target_id: str, edge_type: EdgeType, **properties) -> Edge:
        """Convenience: create and add an edge."""
        edge = Edge(source_id=source_id, target_id=target_id, type=edge_type, properties=properties)
        return self.add_edge(edge)

    def edges_from(self, node_id: str, edge_type: Optional[EdgeType] = None) -> list[Edge]:
        edges = self._outgoing.get(node_id, [])
        if edge_type:
            edges = [e for e in edges if e.type == edge_type]
        return edges

    def edges_to(self, node_id: str, edge_type: Optional[EdgeType] = None) -> list[Edge]:
        edges = self._incoming.get(node_id, [])
        if edge_type:
            edges = [e for e in edges if e.type == edge_type]
        return edges

    # ─── TRAVERSAL ───

    def trace_provenance(self, node_id: str, max_depth: int = 10) -> dict:
        """
        Full provenance trace from any node.
        Walks backward through incoming edges to reconstruct
        the complete decision chain.
        """
        visited = set()
        trace = {"root": node_id, "chain": [], "depth": 0}

        def walk(nid, depth):
            if nid in visited or depth > max_depth:
                return
            visited.add(nid)
            trace["depth"] = max(trace["depth"], depth)

            node = self.get_node(nid)
            if not node:
                return

            step = {
                "node_id": nid,
                "type": node.type.value,
                "depth": depth,
                "properties": node.properties,
                "incoming": [],
            }

            for edge in self.edges_to(nid):
                source = self.get_node(edge.source_id)
                step["incoming"].append({
                    "from": edge.source_id,
                    "edge_type": edge.type.value,
                    "from_type": source.type.value if source else "unknown",
                    "edge_properties": edge.properties,
                })
                walk(edge.source_id, depth + 1)

            trace["chain"].append(step)

        walk(node_id, 0)
        return trace

    def trace_impact(self, node_id: str, max_depth: int = 10) -> dict:
        """
        Forward impact trace — what was affected by this node.
        Walks forward through outgoing edges.
        """
        visited = set()
        trace = {"root": node_id, "impacted": [], "depth": 0}

        def walk(nid, depth):
            if nid in visited or depth > max_depth:
                return
            visited.add(nid)
            trace["depth"] = max(trace["depth"], depth)

            node = self.get_node(nid)
            if not node:
                return

            for edge in self.edges_from(nid):
                target = self.get_node(edge.target_id)
                trace["impacted"].append({
                    "node_id": edge.target_id,
                    "type": target.type.value if target else "unknown",
                    "edge_type": edge.type.value,
                    "depth": depth + 1,
                })
                walk(edge.target_id, depth + 1)

        walk(node_id, 0)
        return trace

    # ─── QUERIES ───

    def query_domain_stats(self, domain: str) -> dict:
        """Convergence stats for a domain."""
        domain_deeds = []
        for edge in self._outgoing.get(f"domain:{domain}", []):
            if edge.type == EdgeType.BELONGS_TO:
                continue
        # Find all deeds in this domain
        for nid in self._type_index.get(NodeType.DEED, []):
            deed = self.nodes[nid]
            if deed.properties.get("domain") == domain:
                domain_deeds.append(deed)

        if not domain_deeds:
            return {"domain": domain, "count": 0}

        scores = [d.properties.get("final_score", 0) for d in domain_deeds]
        tiers = defaultdict(int)
        for d in domain_deeds:
            tiers[d.properties.get("tier", "unknown")] += 1

        return {
            "domain": domain,
            "total_deeds": len(domain_deeds),
            "mean_score": round(sum(scores) / len(scores), 4),
            "min_score": round(min(scores), 4),
            "max_score": round(max(scores), 4),
            "tiers": dict(tiers),
            "rj_yield": round(tiers.get("royal_jelly", 0) / len(domain_deeds), 4),
        }

    def query_judge_calibration(self, judge_id: str) -> dict:
        """Check judge scoring consistency over time."""
        scores = []
        for edge in self.edges_from(judge_id, EdgeType.SCORED_BY):
            if "score" in edge.properties:
                scores.append(edge.properties["score"])

        if not scores:
            return {"judge": judge_id, "total_scores": 0}

        # Split into windows
        window_size = max(len(scores) // 10, 1)
        windows = [scores[i:i + window_size] for i in range(0, len(scores), window_size)]
        window_means = [sum(w) / len(w) for w in windows if w]

        drift = abs(window_means[-1] - window_means[0]) if len(window_means) > 1 else 0

        return {
            "judge": judge_id,
            "total_scores": len(scores),
            "overall_mean": round(sum(scores) / len(scores), 4),
            "window_means": [round(m, 4) for m in window_means],
            "drift": round(drift, 4),
            "calibrated": drift < 0.05,
        }

    def query_model_provenance(self, writer_id: str) -> dict:
        """Complete provenance chain for a writer model."""
        writer = self.get_node(writer_id)
        if not writer:
            return {"error": f"Writer {writer_id} not found"}

        # What deeds trained this writer?
        trained_edges = self.edges_from(writer_id, EdgeType.TRAINED_ON)
        deed_ids = [e.target_id for e in trained_edges]

        # What judges scored those deeds?
        judge_ids = set()
        anchor_ids = set()
        for deed_id in deed_ids:
            for e in self.edges_to(deed_id, EdgeType.SCORED_BY):
                judge_ids.add(e.source_id)
            # Walk to batch → anchor
            for e in self.edges_from(deed_id, EdgeType.IN_BATCH):
                batch_id = e.target_id
                for ae in self.edges_from(batch_id, EdgeType.ANCHORED_TO):
                    anchor_ids.add(ae.target_id)

        return {
            "writer": writer_id,
            "model": writer.properties.get("model", ""),
            "trained_on_deeds": len(deed_ids),
            "judged_by": list(judge_ids),
            "anchored_to": list(anchor_ids),
            "provenance_depth": 5,  # pair → judge → deed → batch → anchor
            "verifiable": len(anchor_ids) > 0,
        }

    # ─── INGEST ───

    def ingest_deeds(self, deeds_path: str, domain: str = "unknown"):
        """Ingest scored and deeded pairs into the graph."""

        # Ensure domain node exists
        domain_node = self.add_node(Node(
            id=f"domain:{domain}",
            type=NodeType.DOMAIN,
            properties={"name": domain},
        ))

        count = 0
        with open(deeds_path) as f:
            for line in f:
                if not line.strip():
                    continue
                data = json.loads(line)
                tribunal = data.get("tribunal", {})
                if not tribunal:
                    continue

                block_id = tribunal["block_id"]
                fp = tribunal.get("fingerprint", "")

                # Add PAIR node
                pair_node = self.add_node(Node(
                    id=f"pair:{fp[:16]}",
                    type=NodeType.PAIR,
                    properties={
                        "fingerprint": fp,
                        "domain": domain,
                    },
                ))

                # Add DEED node
                deed_node = self.add_node(Node(
                    id=f"deed:{block_id}",
                    type=NodeType.DEED,
                    properties={
                        "block_id": block_id,
                        "final_score": tribunal["final_score"],
                        "tier": tribunal["classification"]["tier"],
                        "max_drift": tribunal.get("max_drift", 0),
                        "validated": tribunal.get("validated", True),
                        "domain": domain,
                        "sealed_at": tribunal["sealed_at"],
                    },
                ))

                # Add JUDGE nodes (idempotent)
                judge_a = tribunal["judge_a"]
                judge_b = tribunal["judge_b"]

                ja_node = self.add_node(Node(
                    id=f"judge:{judge_a['label']}",
                    type=NodeType.JUDGE,
                    properties={
                        "model": judge_a["model"],
                        "label": judge_a["label"],
                        "modified": False,
                        "deterministic": True,
                    },
                ))

                jb_node = self.add_node(Node(
                    id=f"judge:{judge_b['label']}",
                    type=NodeType.JUDGE,
                    properties={
                        "model": judge_b["model"],
                        "label": judge_b["label"],
                        "modified": False,
                        "deterministic": True,
                    },
                ))

                # Connect: Pair → Judges (SCORED_BY)
                self.connect(pair_node.id, ja_node.id, EdgeType.SCORED_BY,
                             score=judge_a["score"], reasoning=judge_a.get("reasoning", ""),
                             pass_1=judge_a.get("pass_1"), pass_2=judge_a.get("pass_2"))
                self.connect(pair_node.id, jb_node.id, EdgeType.SCORED_BY,
                             score=judge_b["score"], reasoning=judge_b.get("reasoning", ""))

                # Connect: Pair → Deed (DEEDED_AS)
                self.connect(pair_node.id, deed_node.id, EdgeType.DEEDED_AS,
                             tier=tribunal["classification"]["tier"])

                # Connect: Pair → Domain (BELONGS_TO)
                self.connect(pair_node.id, domain_node.id, EdgeType.BELONGS_TO)

                count += 1

        self.stats["deeds_ingested"] += count
        print(f"[swarmgraph] Ingested {count:,} deeds from {domain}")
        return count

    def ingest_anchors(self, manifest_path: str):
        """Ingest Merkle batch anchors into the graph."""
        with open(manifest_path) as f:
            manifest = json.load(f)

        for batch in manifest.get("batches", []):
            batch_node = self.add_node(Node(
                id=f"batch:{batch['batch_index']}",
                type=NodeType.BATCH,
                properties={
                    "merkle_root": batch["merkle_root"],
                    "leaf_count": batch["leaf_count"],
                    "block_range": batch["block_range"],
                },
            ))

        receipts = manifest.get("receipts", [])
        for receipt in receipts:
            if receipt.get("status") == "submitted":
                anchor_node = self.add_node(Node(
                    id=f"anchor:{receipt['topic']}:{receipt.get('sequence', 0)}",
                    type=NodeType.ANCHOR,
                    properties={
                        "topic": receipt["topic"],
                        "merkle_root": receipt["merkle_root"],
                        "verify_url": receipt.get("verify", ""),
                    },
                ))

    def register_writer(self, writer_id: str, model: str, deed_ids: list[str],
                        silicon_id: str = None):
        """Register a writer model and connect it to its training deeds."""
        writer_node = self.add_node(Node(
            id=f"writer:{writer_id}",
            type=NodeType.WRITER,
            properties={"model": model, "trained_on_count": len(deed_ids)},
        ))

        for deed_id in deed_ids:
            self.connect(writer_node.id, deed_id, EdgeType.TRAINED_ON)

        if silicon_id:
            self.connect(writer_node.id, silicon_id, EdgeType.RAN_ON)

        print(f"[swarmgraph] Registered writer {writer_id} → {len(deed_ids):,} deeds")

    def register_silicon(self, silicon_id: str, hardware: str, arch: str,
                         power_watts: int, location: str = "datacenter"):
        """Register a hardware node."""
        return self.add_node(Node(
            id=f"silicon:{silicon_id}",
            type=NodeType.SILICON,
            properties={
                "hardware": hardware,
                "arch": arch,
                "power_watts": power_watts,
                "location": location,
            },
        ))

    # ─── EXPORT ───

    def summary(self) -> dict:
        """Graph summary statistics."""
        type_counts = {t.value: len(ids) for t, ids in self._type_index.items() if ids}
        deed_nodes = self.nodes_by_type(NodeType.DEED)
        tier_counts = defaultdict(int)
        for d in deed_nodes:
            tier_counts[d.properties.get("tier", "unknown")] += 1

        return {
            "name": self.name,
            "total_nodes": len(self.nodes),
            "total_edges": len(self.edges),
            "node_types": type_counts,
            "tier_distribution": dict(tier_counts),
            "stats": self.stats,
            "created_at": self.created_at,
        }

    def export_json(self, output_path: str):
        """Export the full graph as JSON."""
        data = {
            "name": self.name,
            "version": "1.0",
            "summary": self.summary(),
            "nodes": [
                {"id": n.id, "type": n.type.value, "properties": n.properties, "created_at": n.created_at}
                for n in self.nodes.values()
            ],
            "edges": [
                {"source": e.source_id, "target": e.target_id, "type": e.type.value, "properties": e.properties}
                for e in self.edges
            ],
        }
        with open(output_path, "w") as f:
            json.dump(data, f, indent=2)
        print(f"[swarmgraph] Exported to {output_path} ({len(self.nodes):,} nodes, {len(self.edges):,} edges)")

    def __repr__(self):
        return f"SwarmGraph(nodes={len(self.nodes)}, edges={len(self.edges)})"
