"""
SwarmGraph Node and Edge Type Definitions
==========================================
The schema of the context graph. Domain-agnostic.
Same types for medical, CRE, aviation, grants — any domain.
"""
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional


class NodeType(str, Enum):
    PAIR = "pair"
    DEED = "deed"
    JUDGE = "judge"
    WRITER = "writer"
    BLOCK = "block"
    BATCH = "batch"
    ANCHOR = "anchor"
    DOMAIN = "domain"
    SILICON = "silicon"
    EPOCH = "epoch"
    CALIBRATION = "calibration"


class EdgeType(str, Enum):
    SCORED_BY = "scored_by"           # Pair → Judge
    DEEDED_AS = "deeded_as"           # Pair → Deed
    PRODUCED_BY = "produced_by"       # Pair → Writer
    IN_BLOCK = "in_block"             # Deed → Block
    IN_BATCH = "in_batch"             # Deed → Batch
    ANCHORED_TO = "anchored_to"       # Batch → Anchor
    TRAINED_ON = "trained_on"         # Writer → Deed
    RAN_ON = "ran_on"                 # Judge/Writer → Silicon
    BELONGS_TO = "belongs_to"         # Pair → Domain
    IMPROVED_FROM = "improved_from"   # Deed → Deed (re-score)
    CONVERGES_WITH = "converges_with" # Epoch → Epoch
    CALIBRATED_AT = "calibrated_at"   # Judge → Calibration
    COSTS = "costs"                   # Deed → Silicon (economics)


@dataclass
class Node:
    """A node in the SwarmGraph."""
    id: str
    type: NodeType
    properties: dict = field(default_factory=dict)
    created_at: Optional[str] = None

    def __hash__(self):
        return hash(self.id)

    def __eq__(self, other):
        return isinstance(other, Node) and self.id == other.id


@dataclass
class Edge:
    """A directed edge in the SwarmGraph."""
    source_id: str
    target_id: str
    type: EdgeType
    properties: dict = field(default_factory=dict)

    @property
    def key(self):
        return (self.source_id, self.target_id, self.type)
