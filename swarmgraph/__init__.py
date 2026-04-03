"""
SwarmGraph — Context Graph for AI Training Data
================================================
Every node is a decision. Every edge is provenance.
Every anchor is permanent. Pull any node — full trace.

    from swarmgraph import SwarmGraph
    g = SwarmGraph()
    g.ingest_deeds("domains/medical/deeds/deeds.jsonl")
    g.query_provenance("SB-2026-0402-00001")
"""
from .graph import SwarmGraph
from .nodes import NodeType, EdgeType

__version__ = "1.0.0"
__all__ = ["SwarmGraph", "NodeType", "EdgeType"]
