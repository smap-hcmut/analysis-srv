"""Ontology domain types — Pydantic models matching core-analysis.

Aligned with core-analysis smap/ontology/models.py.
Uses Pydantic BaseModel with model_validator for cross-reference validation.
Knowledge layers: "base" | "domain" | "domain_overlay" | "review_overlay" | "batch_local_candidate"
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

# ---------------------------------------------------------------------------
# Type aliases
# ---------------------------------------------------------------------------

OverlayProvenanceValue = str | int | float | bool | None
KnowledgeLayerKind = Literal[
    "base", "domain", "domain_overlay", "review_overlay", "batch_local_candidate"
]
EntityKind = Literal["entity", "concept"]

# Shared intent category IDs that every ontology must include.
SHARED_INTENT_CATEGORY_IDS = frozenset(
    {"question", "complaint", "commentary", "praise", "purchase_intent", "compare"}
)

# Shared entity type IDs that every ontology must include.
SHARED_ENTITY_TYPE_IDS = frozenset(
    {
        "brand",
        "product",
        "person",
        "organization",
        "location",
        "facility",
        "retailer",
        "concept",
    }
)


# ---------------------------------------------------------------------------
# Ontology building blocks
# ---------------------------------------------------------------------------


class OntologyMetadata(BaseModel):
    name: str
    version: str
    description: str = ""


class TaxonomyNode(BaseModel):
    id: str
    label: str
    node_type: str  # "category" | "feature"
    parent_id: str | None = None
    description: str | None = None


class CategoryDefinition(BaseModel):
    """Used for aspect_categories, intent_categories, and issue_categories."""

    id: str
    label: str
    description: str | None = None
    seed_phrases: list[str] = Field(default_factory=list)
    negative_phrases: list[str] = Field(default_factory=list)
    compatible_entity_types: list[str] = Field(default_factory=list)
    linked_topic_keys: list[str] = Field(default_factory=list)
    related_issue_ids: list[str] = Field(default_factory=list)
    related_aspect_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, OverlayProvenanceValue] = Field(default_factory=dict)


class TopicDefinition(BaseModel):
    topic_key: str
    label: str
    description: str | None = None
    knowledge_layer: KnowledgeLayerKind = "base"
    topic_family: str | None = None
    main_path_policy: Literal["core", "domain_primary", "discovery_only"] = "core"
    seed_phrases: list[str] = Field(default_factory=list)
    negative_phrases: list[str] = Field(default_factory=list)
    domain_tags: list[str] = Field(default_factory=list)
    excluded_domain_tags: list[str] = Field(default_factory=list)
    issue_centric: bool = False
    reportable: bool = True
    related_entity_ids: list[str] = Field(default_factory=list)
    related_taxonomy_ids: list[str] = Field(default_factory=list)
    related_aspect_ids: list[str] = Field(default_factory=list)
    related_issue_ids: list[str] = Field(default_factory=list)
    compatible_entity_types: list[str] = Field(default_factory=list)
    metadata: dict[str, OverlayProvenanceValue] = Field(default_factory=dict)

    @field_validator("main_path_policy", mode="before")
    @classmethod
    def normalize_main_path_policy(cls, value: object) -> object:
        if value == "generic_fallback":
            return "core"
        return value


class EntitySeed(BaseModel):
    """A canonical entity (brand, product, person, ...).

    Aligned with core-analysis EntitySeed — full-featured model.
    """

    id: str
    name: str
    entity_type: str
    entity_kind: EntityKind = "entity"
    knowledge_layer: KnowledgeLayerKind = "base"
    active_linking: bool = True
    target_eligible: bool = True
    aliases: list[str] = Field(default_factory=list)
    compact_aliases: list[str] = Field(default_factory=list)
    taxonomy_ids: list[str] = Field(default_factory=list)
    description: str | None = None
    related_phrases: list[str] = Field(default_factory=list)
    domain_anchor_phrases: list[str] = Field(default_factory=list)
    neighboring_entity_ids: list[str] = Field(default_factory=list)
    neighboring_aspect_ids: list[str] = Field(default_factory=list)
    anti_confusion_phrases: list[str] = Field(default_factory=list)
    metadata: dict[str, OverlayProvenanceValue] = Field(default_factory=dict)


class SourceChannel(BaseModel):
    id: str
    label: str


# ---------------------------------------------------------------------------
# Overlay types
# ---------------------------------------------------------------------------


class OntologyOverlayMetadata(BaseModel):
    name: str
    version: str
    description: str | None = None
    source: str = "manual"
    layer_kind: KnowledgeLayerKind = "domain_overlay"


class OverlayActivationSignal(BaseModel):
    phrase: str
    weight: float = 1.0


class OverlayActivationProfile(BaseModel):
    primary_min_score: float | None = None
    primary_min_matched_records: int | None = None
    secondary_min_score: float | None = None
    secondary_min_matched_records: int | None = None
    signals: list[OverlayActivationSignal] = Field(default_factory=list)


class AliasContribution(BaseModel):
    canonical_entity_id: str
    alias: str
    entity_type: str | None = None
    source: str = "overlay"
    provenance: dict[str, OverlayProvenanceValue] = Field(default_factory=dict)


class NoiseTerm(BaseModel):
    term: str
    reason: str
    source: str = "overlay"
    provenance: dict[str, OverlayProvenanceValue] = Field(default_factory=dict)


class OntologyOverlay(BaseModel):
    """An overlay that extends a base ontology registry."""

    metadata: OntologyOverlayMetadata
    activation: OverlayActivationProfile | None = None
    entities: list[EntitySeed] = Field(default_factory=list)
    aspect_categories: list[CategoryDefinition] = Field(default_factory=list)
    issue_categories: list[CategoryDefinition] = Field(default_factory=list)
    topics: list[TopicDefinition] = Field(default_factory=list)
    alias_contributions: list[AliasContribution] = Field(default_factory=list)
    noise_terms: list[NoiseTerm] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Main registry
# ---------------------------------------------------------------------------


class OntologyRegistry(BaseModel):
    """Full ontology registry — the single source of truth for a domain.

    Aligned with core-analysis OntologyRegistry. Includes model_validator
    for cross-reference validation of all linked IDs.
    """

    metadata: OntologyMetadata
    domain_id: str | None = None
    activation: OverlayActivationProfile | None = None

    entity_types: list[str]
    taxonomy_nodes: list[TaxonomyNode]
    aspect_categories: list[CategoryDefinition]
    intent_categories: list[CategoryDefinition]
    issue_categories: list[CategoryDefinition]
    source_channels: list[SourceChannel]

    entities: list[EntitySeed] = Field(default_factory=list)
    topics: list[TopicDefinition] = Field(default_factory=list)
    alias_contributions: list[AliasContribution] = Field(default_factory=list)
    noise_terms: list[NoiseTerm] = Field(default_factory=list)
    loaded_overlays: list[OntologyOverlayMetadata] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_registry(self) -> "OntologyRegistry":
        node_ids = {node.id for node in self.taxonomy_nodes}
        aspect_ids = {cat.id for cat in self.aspect_categories}
        intent_ids = {cat.id for cat in self.intent_categories}
        issue_ids = {cat.id for cat in self.issue_categories}
        entity_ids = {entity.id for entity in self.entities}
        topic_keys = {topic.topic_key for topic in self.topics}

        # Shared entity types
        missing_types = sorted(SHARED_ENTITY_TYPE_IDS - set(self.entity_types))
        if missing_types:
            raise ValueError(f"ontology missing shared entity types {missing_types}")

        # Shared intent categories
        missing_intents = sorted(SHARED_INTENT_CATEGORY_IDS - intent_ids)
        if missing_intents:
            raise ValueError(
                f"ontology missing shared intent categories {missing_intents}"
            )

        # Taxonomy parent references
        for node in self.taxonomy_nodes:
            if node.parent_id and node.parent_id not in node_ids:
                raise ValueError(
                    f"taxonomy node {node.id} references missing parent {node.parent_id}"
                )

        # Entity references
        for entity in self.entities:
            if entity.entity_type not in self.entity_types:
                raise ValueError(
                    f"entity {entity.id} references unknown entity type {entity.entity_type}"
                )
            missing_tax = [t for t in entity.taxonomy_ids if t not in node_ids]
            if missing_tax:
                raise ValueError(
                    f"entity {entity.id} references unknown taxonomy ids {missing_tax}"
                )
            missing_neighbors = [
                e for e in entity.neighboring_entity_ids if e not in entity_ids
            ]
            if missing_neighbors:
                raise ValueError(
                    f"entity {entity.id} references unknown neighboring entities {missing_neighbors}"
                )
            missing_aspects = [
                a for a in entity.neighboring_aspect_ids if a not in aspect_ids
            ]
            if missing_aspects:
                raise ValueError(
                    f"entity {entity.id} references unknown neighboring aspects {missing_aspects}"
                )

        # Topic references
        for topic in self.topics:
            missing_ent = [e for e in topic.related_entity_ids if e not in entity_ids]
            if missing_ent:
                raise ValueError(
                    f"topic {topic.topic_key} references unknown entities {missing_ent}"
                )
            missing_tax = [t for t in topic.related_taxonomy_ids if t not in node_ids]
            if missing_tax:
                raise ValueError(
                    f"topic {topic.topic_key} references unknown taxonomy ids {missing_tax}"
                )
            missing_asp = [a for a in topic.related_aspect_ids if a not in aspect_ids]
            if missing_asp:
                raise ValueError(
                    f"topic {topic.topic_key} references unknown aspects {missing_asp}"
                )
            missing_iss = [i for i in topic.related_issue_ids if i not in issue_ids]
            if missing_iss:
                raise ValueError(
                    f"topic {topic.topic_key} references unknown issues {missing_iss}"
                )

        # Aspect references
        for cat in self.aspect_categories:
            missing_topics = [t for t in cat.linked_topic_keys if t not in topic_keys]
            if missing_topics:
                raise ValueError(
                    f"aspect {cat.id} references unknown topics {missing_topics}"
                )
            missing_iss = [i for i in cat.related_issue_ids if i not in issue_ids]
            if missing_iss:
                raise ValueError(
                    f"aspect {cat.id} references unknown issues {missing_iss}"
                )

        # Issue references
        for cat in self.issue_categories:
            missing_topics = [t for t in cat.linked_topic_keys if t not in topic_keys]
            if missing_topics:
                raise ValueError(
                    f"issue {cat.id} references unknown topics {missing_topics}"
                )
            missing_asp = [a for a in cat.related_aspect_ids if a not in aspect_ids]
            if missing_asp:
                raise ValueError(
                    f"issue {cat.id} references unknown aspects {missing_asp}"
                )

        # Alias contribution references
        for alias in self.alias_contributions:
            if alias.canonical_entity_id not in entity_ids:
                raise ValueError(
                    f"alias contribution for unknown entity {alias.canonical_entity_id}"
                )
            if (
                alias.entity_type is not None
                and alias.entity_type not in self.entity_types
            ):
                raise ValueError(
                    f"alias contribution references unknown entity type {alias.entity_type}"
                )

        return self

    # -- Convenience properties --

    @property
    def taxonomy_node_ids(self) -> set[str]:
        return {node.id for node in self.taxonomy_nodes}

    @property
    def aspect_category_ids(self) -> set[str]:
        return {cat.id for cat in self.aspect_categories}

    @property
    def intent_category_ids(self) -> set[str]:
        return {cat.id for cat in self.intent_categories}

    @property
    def issue_category_ids(self) -> set[str]:
        return {cat.id for cat in self.issue_categories}

    @property
    def source_channel_ids(self) -> set[str]:
        return {ch.id for ch in self.source_channels}

    @property
    def entity_ids(self) -> set[str]:
        return {e.id for e in self.entities}

    @property
    def topic_keys(self) -> set[str]:
        return {t.topic_key for t in self.topics}


__all__ = [
    "OverlayProvenanceValue",
    "KnowledgeLayerKind",
    "EntityKind",
    "SHARED_INTENT_CATEGORY_IDS",
    "SHARED_ENTITY_TYPE_IDS",
    "OntologyMetadata",
    "TaxonomyNode",
    "CategoryDefinition",
    "TopicDefinition",
    "EntitySeed",
    "SourceChannel",
    "OntologyOverlayMetadata",
    "OverlayActivationSignal",
    "OverlayActivationProfile",
    "AliasContribution",
    "NoiseTerm",
    "OntologyOverlay",
    "OntologyRegistry",
]
