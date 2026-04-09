"""FileOntologyRegistry — loads entities, taxonomy and source channels from YAML files.

Replaces OntologyRegistryStub.  Satisfies the interface expected by:
  - build_marts.build_mart_bundle() — reads .entities, .taxonomy_nodes, .source_channels
  - reporting/type.py ReportingInput.ontology field

Usage:
    registry = FileOntologyRegistry.from_config(config.ontology)
    # registry.entities       → list[OntologyEntity]
    # registry.taxonomy_nodes → list[TaxonomyNode]
    # registry.source_channels → list[SourceChannel]
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

from internal.ontology.type import OntologyEntity, TaxonomyNode, SourceChannel

if TYPE_CHECKING:
    from config.config import OntologyConfig


@dataclass
class FileOntologyRegistry:
    """YAML-backed ontology registry.

    Loaded once at startup.  Immutable after construction.
    To refresh, restart the service (or call FileOntologyRegistry.from_config again).
    """

    entities: list[OntologyEntity] = field(default_factory=list)
    taxonomy_nodes: list[TaxonomyNode] = field(default_factory=list)
    source_channels: list[SourceChannel] = field(default_factory=list)

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def from_config(cls, config: "OntologyConfig") -> "FileOntologyRegistry":
        """Load all three YAML files and return a populated registry.

        Missing files are tolerated with a warning: the corresponding list
        will be empty so the pipeline continues in degraded mode.
        """
        entities = cls._load_entities(config.entities_path)
        taxonomy_nodes = cls._load_taxonomy(config.taxonomy_path)
        source_channels = cls._load_source_channels(config.source_channels_path)
        return cls(
            entities=entities,
            taxonomy_nodes=taxonomy_nodes,
            source_channels=source_channels,
        )

    # ------------------------------------------------------------------
    # Internal loaders
    # ------------------------------------------------------------------

    @staticmethod
    def _read_yaml(path: str) -> dict:
        """Read a YAML file.  Returns empty dict if file not found."""
        p = Path(path)
        if not p.exists():
            return {}
        with p.open(encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    @classmethod
    def _load_entities(cls, path: str) -> list[OntologyEntity]:
        data = cls._read_yaml(path)
        raw: list[dict] = data.get("entities", [])
        result: list[OntologyEntity] = []
        for item in raw:
            try:
                result.append(
                    OntologyEntity(
                        id=item["id"],
                        name=item["name"],
                        entity_type=item.get("entity_type", "other"),
                        entity_kind=item.get("entity_kind", "generic"),
                        knowledge_layer=item.get("knowledge_layer", "L3"),
                        active_linking=item.get("active_linking", True),
                        taxonomy_ids=item.get("taxonomy_ids", []),
                        aliases=item.get("aliases", []),
                    )
                )
            except (KeyError, ValueError):
                # Skip malformed entries — log at DEBUG if logger is available
                continue
        return result

    @classmethod
    def _load_taxonomy(cls, path: str) -> list[TaxonomyNode]:
        data = cls._read_yaml(path)
        raw: list[dict] = data.get("taxonomy", [])
        result: list[TaxonomyNode] = []
        for item in raw:
            try:
                result.append(
                    TaxonomyNode(
                        id=item["id"],
                        name=item["name"],
                        parent_id=item.get("parent_id"),
                        level=item.get("level", 0),
                        path=item.get("path", item["id"]),
                    )
                )
            except (KeyError, ValueError):
                continue
        return result

    @classmethod
    def _load_source_channels(cls, path: str) -> list[SourceChannel]:
        data = cls._read_yaml(path)
        raw: list[dict] = data.get("source_channels", [])
        result: list[SourceChannel] = []
        for item in raw:
            try:
                result.append(
                    SourceChannel(
                        id=item["id"],
                        name=item["name"],
                        platform=item.get("platform", item["id"]),
                        url=item.get("url", ""),
                        active=item.get("active", True),
                    )
                )
            except (KeyError, ValueError):
                continue
        return result

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def entity_by_id(self, entity_id: str) -> OntologyEntity | None:
        """Return entity by canonical ID, or None."""
        for e in self.entities:
            if e.id == entity_id:
                return e
        return None

    def entities_for_taxonomy(self, taxonomy_id: str) -> list[OntologyEntity]:
        """Return all entities that belong to a given taxonomy node."""
        return [e for e in self.entities if taxonomy_id in e.taxonomy_ids]

    def active_entities(self) -> list[OntologyEntity]:
        """Return only entities with active_linking=True."""
        return [e for e in self.entities if e.active_linking]

    def alias_map(self) -> dict[str, OntologyEntity]:
        """Return a flat alias → entity mapping for fast lookup.

        If two entities share an alias, the last one wins.
        """
        result: dict[str, OntologyEntity] = {}
        for entity in self.entities:
            for alias in entity.aliases:
                result[alias.lower()] = entity
            result[entity.name.lower()] = entity
        return result

    def __repr__(self) -> str:
        return (
            f"FileOntologyRegistry("
            f"entities={len(self.entities)}, "
            f"taxonomy_nodes={len(self.taxonomy_nodes)}, "
            f"source_channels={len(self.source_channels)})"
        )


__all__ = ["FileOntologyRegistry"]
