"""FileOntologyRegistry — loads a self-contained domain ontology YAML.

Aligned with core-analysis ontology loading.  Each domain has ONE YAML file
that contains the complete OntologyRegistry (entities, taxonomy, aspects,
issues, intents, topics, etc.).

Usage:
    registry = FileOntologyRegistry.from_yaml("config/ontology/vinfast_vn.yaml")
    # registry.ontology  → OntologyRegistry (Pydantic)
    # registry.entities  → list[EntitySeed]
    # registry.alias_map() → dict[str, EntitySeed]
"""

from __future__ import annotations

import logging
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

from internal.ontology.type import (
    EntitySeed,
    OntologyOverlay,
    OntologyRegistry,
    TaxonomyNode,
    SourceChannel,
    CategoryDefinition,
    TopicDefinition,
)

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


def _read_yaml(path: Path) -> dict:
    """Read a YAML file and return parsed dict."""
    if not path.exists():
        logger.warning("Ontology file not found: %s", path)
        return {}
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def normalize_alias(text: str) -> str:
    """Normalize an alias string for matching: lowercase, strip punctuation, collapse whitespace."""
    text = text.lower().strip()
    text = re.sub(r"[#@\"'`]", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


@dataclass
class FileOntologyRegistry:
    """YAML-backed ontology registry using core-analysis's OntologyRegistry model.

    Loaded once at startup.  Immutable after construction.
    """

    ontology: OntologyRegistry
    _alias_cache: dict[str, EntitySeed] | None = field(
        default=None, repr=False, compare=False
    )

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def from_yaml(cls, path: str) -> "FileOntologyRegistry":
        """Load a self-contained domain ontology YAML into OntologyRegistry.

        The YAML must conform to the OntologyRegistry Pydantic schema.
        Validation (including cross-reference checks) happens automatically.
        """
        yaml_path = Path(path)
        data = _read_yaml(yaml_path)
        if not data:
            raise ValueError(f"Empty or missing ontology file: {path}")

        registry = OntologyRegistry.model_validate(data)

        logger.info(
            "FileOntologyRegistry: loaded %s v%s — "
            "%d entities, %d aspects, %d issues, %d intents, %d topics, "
            "%d taxonomy nodes, %d source channels",
            registry.metadata.name,
            registry.metadata.version,
            len(registry.entities),
            len(registry.aspect_categories),
            len(registry.issue_categories),
            len(registry.intent_categories),
            len(registry.topics),
            len(registry.taxonomy_nodes),
            len(registry.source_channels),
        )
        return cls(ontology=registry)

    @classmethod
    def from_config(cls, ontology_config: object) -> "FileOntologyRegistry":
        """Load from an OntologyConfig dataclass (config.config.OntologyConfig).

        Uses the new ``domain_ontology_path`` field for the self-contained
        YAML.  Falls back to the legacy 3-file path if the domain file is
        not found (but raises on empty content).
        """
        domain_path = getattr(ontology_config, "domain_ontology_path", None)
        if domain_path and Path(domain_path).exists():
            return cls.from_yaml(domain_path)
        # Fallback: try legacy path — but warn
        logger.warning(
            "domain_ontology_path %s not found, cannot load ontology",
            domain_path,
        )
        raise ValueError(
            f"Ontology domain file not found: {domain_path}. "
            "Ensure config/ontology/vinfast_vn.yaml exists."
        )

    @classmethod
    def from_yaml_with_overlays(
        cls,
        base_path: str,
        overlay_paths: Sequence[str] | None = None,
    ) -> "FileOntologyRegistry":
        """Load a base ontology and apply overlay files on top.

        Overlays can add/replace entities, aspects, issues, topics,
        alias contributions, and noise terms.
        """
        yaml_path = Path(base_path)
        data = _read_yaml(yaml_path)
        if not data:
            raise ValueError(f"Empty or missing ontology file: {base_path}")

        registry = OntologyRegistry.model_validate(data)

        if overlay_paths:
            overlays = []
            for overlay_path in overlay_paths:
                overlay_data = _read_yaml(Path(overlay_path))
                if overlay_data:
                    overlays.append(OntologyOverlay.model_validate(overlay_data))

            if overlays:
                registry = _apply_overlays(registry, overlays)

        logger.info(
            "FileOntologyRegistry: loaded %s v%s with %d overlay(s)",
            registry.metadata.name,
            registry.metadata.version,
            len(registry.loaded_overlays),
        )
        return cls(ontology=registry)

    # ------------------------------------------------------------------
    # Properties — convenience access matching old interface
    # ------------------------------------------------------------------

    @property
    def entities(self) -> list[EntitySeed]:
        return self.ontology.entities

    @property
    def taxonomy_nodes(self) -> list[TaxonomyNode]:
        return self.ontology.taxonomy_nodes

    @property
    def source_channels(self) -> list[SourceChannel]:
        return self.ontology.source_channels

    @property
    def aspect_categories(self) -> list[CategoryDefinition]:
        return self.ontology.aspect_categories

    @property
    def intent_categories(self) -> list[CategoryDefinition]:
        return self.ontology.intent_categories

    @property
    def issue_categories(self) -> list[CategoryDefinition]:
        return self.ontology.issue_categories

    @property
    def topics(self) -> list[TopicDefinition]:
        return self.ontology.topics

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def entity_by_id(self, entity_id: str) -> EntitySeed | None:
        """Return entity by canonical ID, or None."""
        for e in self.ontology.entities:
            if e.id == entity_id:
                return e
        return None

    def entities_for_taxonomy(self, taxonomy_id: str) -> list[EntitySeed]:
        """Return all entities that belong to a given taxonomy node."""
        return [e for e in self.ontology.entities if taxonomy_id in e.taxonomy_ids]

    def active_entities(self) -> list[EntitySeed]:
        """Return only entities with active_linking=True."""
        return [e for e in self.ontology.entities if e.active_linking]

    def alias_map(self) -> dict[str, EntitySeed]:
        """Return a flat alias → entity mapping for fast lookup.

        Includes: name, aliases, compact_aliases (all normalized).
        If two entities share an alias, the last one wins.
        """
        if self._alias_cache is not None:
            return self._alias_cache

        result: dict[str, EntitySeed] = {}
        for entity in self.ontology.entities:
            # Name
            result[normalize_alias(entity.name)] = entity
            # Aliases
            for alias in entity.aliases:
                result[normalize_alias(alias)] = entity
            # Compact aliases
            for alias in entity.compact_aliases:
                result[normalize_alias(alias)] = entity

        # Cache for repeated access
        object.__setattr__(self, "_alias_cache", result)
        return result

    def aspect_seed_phrases(self) -> dict[str, list[str]]:
        """Return aspect_id → seed_phrases mapping for lexical matching."""
        return {
            cat.id: list(cat.seed_phrases) for cat in self.ontology.aspect_categories
        }

    def issue_seed_phrases(self) -> dict[str, list[str]]:
        """Return issue_id → seed_phrases mapping for lexical matching."""
        return {
            cat.id: list(cat.seed_phrases) for cat in self.ontology.issue_categories
        }

    def intent_seed_phrases(self) -> dict[str, list[str]]:
        """Return intent_id → seed_phrases mapping for lexical matching."""
        return {
            cat.id: list(cat.seed_phrases)
            for cat in self.ontology.intent_categories
            if cat.seed_phrases
        }

    def topic_seed_phrases(self) -> dict[str, list[str]]:
        """Return topic_key → seed_phrases mapping."""
        return {
            topic.topic_key: list(topic.seed_phrases) for topic in self.ontology.topics
        }

    def __repr__(self) -> str:
        o = self.ontology
        return (
            f"FileOntologyRegistry("
            f"entities={len(o.entities)}, "
            f"aspects={len(o.aspect_categories)}, "
            f"issues={len(o.issue_categories)}, "
            f"intents={len(o.intent_categories)}, "
            f"topics={len(o.topics)}, "
            f"taxonomy={len(o.taxonomy_nodes)}, "
            f"channels={len(o.source_channels)})"
        )


# ---------------------------------------------------------------------------
# Overlay application (matching core-analysis loader.py)
# ---------------------------------------------------------------------------


def _apply_overlays(
    registry: OntologyRegistry,
    overlays: Sequence[OntologyOverlay],
) -> OntologyRegistry:
    """Apply overlays on top of a base registry (merge by ID/key)."""
    entity_by_id = {e.id: e for e in registry.entities}
    topic_by_key = {t.topic_key: t for t in registry.topics}
    aspect_by_id = {c.id: c for c in registry.aspect_categories}
    issue_by_id = {c.id: c for c in registry.issue_categories}
    alias_contributions = list(registry.alias_contributions)
    noise_terms = list(registry.noise_terms)
    loaded_overlays = list(registry.loaded_overlays)

    for overlay in overlays:
        loaded_overlays.append(overlay.metadata)
        for entity in overlay.entities:
            entity_by_id[entity.id] = entity
        for cat in overlay.aspect_categories:
            aspect_by_id[cat.id] = cat
        for cat in overlay.issue_categories:
            issue_by_id[cat.id] = cat
        for topic in overlay.topics:
            topic_by_key[topic.topic_key] = topic
        alias_contributions.extend(overlay.alias_contributions)
        noise_terms.extend(overlay.noise_terms)

    return OntologyRegistry(
        metadata=registry.metadata,
        domain_id=registry.domain_id,
        activation=registry.activation,
        entity_types=registry.entity_types,
        taxonomy_nodes=registry.taxonomy_nodes,
        aspect_categories=list(aspect_by_id.values()),
        intent_categories=registry.intent_categories,
        issue_categories=list(issue_by_id.values()),
        source_channels=registry.source_channels,
        entities=list(entity_by_id.values()),
        topics=list(topic_by_key.values()),
        alias_contributions=alias_contributions,
        noise_terms=noise_terms,
        loaded_overlays=loaded_overlays,
    )


__all__ = ["FileOntologyRegistry", "normalize_alias"]
