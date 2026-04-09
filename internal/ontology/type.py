"""Ontology domain types.

Dataclasses representing entities, taxonomy nodes and source channels
loaded from YAML files.  These match the attribute access pattern expected
by build_marts.py:
    entity.id, entity.name, entity.entity_type, entity.entity_kind,
    entity.knowledge_layer, entity.active_linking, entity.taxonomy_ids
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class OntologyEntity:
    """A canonical entity (brand, product, person, …)."""

    id: str
    name: str
    entity_type: (
        str  # brand | product | person | organization | location | event | other
    )
    entity_kind: str  # organization | vehicle | feature | service | person | generic
    knowledge_layer: str  # L1 | L2 | L3
    active_linking: bool = True
    taxonomy_ids: list[str] = field(default_factory=list)
    aliases: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("OntologyEntity.id cannot be empty")
        if not self.name:
            raise ValueError("OntologyEntity.name cannot be empty")


@dataclass
class TaxonomyNode:
    """A node in the topic/category hierarchy."""

    id: str
    name: str
    parent_id: str | None
    level: int
    path: str

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("TaxonomyNode.id cannot be empty")

    # build_marts checks hasattr(node, "model_dump") first, falls back to vars()
    # — no model_dump needed; vars() works on dataclasses.


@dataclass
class SourceChannel:
    """A monitored social media / news channel."""

    id: str
    name: str
    platform: str
    url: str = ""
    active: bool = True

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("SourceChannel.id cannot be empty")

    # build_marts also checks hasattr(item, "model_dump"), falls back to vars()


__all__ = ["OntologyEntity", "TaxonomyNode", "SourceChannel"]
