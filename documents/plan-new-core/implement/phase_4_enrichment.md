# Phase 4 — Enrichment (Entity, Semantic, Topic)

> **Depends on:** Phase 3 (produces `MentionRecord[]`, `ThreadBundle`)
> **Source:** `core-analysis/src/smap/enrichers/`
> **New deps:** `faiss-cpu` (vector index), sentence-transformers or local embedding provider

## Mục tiêu

Port `EnricherService` và các enrichers cốt lõi vào `internal/enrichment/`.
Kết quả: `EnrichmentBundle` chứa đầy đủ facts cho Phase 5 (marts + reports).

Enrichment flow (giữ nguyên thứ tự từ `EnricherService.enrich_mentions()`):

```
mentions + contexts
    → Entity extraction (per-mention)
    → annotate_batch_local_candidates (post-batch)
    → Keyword extraction (per-mention)
    → Semantic inference (batch) — sentiment, ABSA, issues, stance, intent
    → Source influence scoring (per-mention)
    → Topic clustering + artifact build (batch)
```

## Folder structure

```
internal/enrichment/
├── interface.py         # IEnrichmentUseCase
├── type.py              # EnrichmentInput, EnrichmentOutput, EnricherConfig
├── constant.py          # ENRICHER_VERSIONS, QUALITY_THRESHOLDS
├── errors.py            # EnrichmentError, EnricherUnavailableError
└── usecase/
    ├── new.py
    ├── usecase.py
    ├── enrich_batch.py          # top-level orchestrator (wraps EnricherService)
    ├── build_enricher_service.py  # factory: assemble EnricherService from config
    ├── entity_enricher.py       # EntityExtractionEnricher wrapper
    ├── semantic_enricher.py     # SemanticInferenceEnricher wrapper
    ├── topic_enricher.py        # TopicCandidateEnricher wrapper
    └── helpers.py               # build_mention_contexts(), mention_to_raw_text()
```

## `type.py`

```python
# internal/enrichment/type.py
from dataclasses import dataclass, field
from smap.enrichers.models import EnrichmentBundle   # ported into internal/
from smap.normalization.models import MentionRecord
from smap.threads.models import ThreadBundle

@dataclass
class EnrichmentInput:
    mentions: list[MentionRecord]
    thread_bundle: ThreadBundle

@dataclass
class EnrichmentOutput:
    bundle: EnrichmentBundle
    enricher_versions: dict[str, str] = field(default_factory=dict)

@dataclass
class EnricherConfig:
    """Feature flags for optional enrichers — controlled via PipelineConfig."""
    entity_enabled: bool = True
    semantic_enabled: bool = True
    topic_enabled: bool = True
    source_influence_enabled: bool = True
    # If False, semantic enricher runs in 'semantic_lite' mode only
    semantic_full_enabled: bool = True
    # Path to fasttext lang model (for normalization stage, referenced here for completeness)
    embedding_model_id: str = "intfloat/multilingual-e5-small"
```

## `enrich_batch.py` — top-level orchestrator

```python
# internal/enrichment/usecase/enrich_batch.py
# Thin wrapper around EnricherService — preserves core-analysis logic exactly

from internal.enrichment.type import EnrichmentInput, EnrichmentOutput, EnricherConfig
from internal.enrichment.usecase.build_enricher_service import build_enricher_service
from internal.enrichment.usecase.helpers import build_mention_contexts

def enrich_batch(
    inp: EnrichmentInput,
    config: EnricherConfig,
) -> EnrichmentOutput:
    """
    Entry point for Phase 4.
    Runs EnricherService on the full batch of MentionRecord[].
    """
    service = build_enricher_service(config)
    contexts = build_mention_contexts(inp.mentions, inp.thread_bundle)

    bundle = service.enrich_mentions(inp.mentions, contexts)

    return EnrichmentOutput(
        bundle=bundle,
        enricher_versions={
            "entity": service.entity_enricher.engine.embedding_provider.version
                      if hasattr(service.entity_enricher, "engine") else "rule-based",
            "semantic": service.semantic_enricher.provider_version,
            "topic": service.topic_enricher.topic_provider.version
                     if hasattr(service.topic_enricher.topic_provider, "version") else "fallback",
        },
    )
```

## `build_enricher_service.py` — factory

```python
# internal/enrichment/usecase/build_enricher_service.py
# Port từ core-analysis/src/smap/enrichers/service.py
# analysis-srv dùng rule-based / lightweight providers (không có LLM tại Phase 4)

from smap.enrichers.service import EnricherService         # ported
from smap.enrichers.entity import EntityExtractionEnricher  # ported
from smap.enrichers.semantic import SemanticInferenceEnricher
from smap.enrichers.topic import TopicCandidateEnricher
from smap.canonicalization.service import CanonicalizationEngine
from smap.canonicalization.alias import AliasRegistry
from smap.providers.fallback import FallbackTopicProvider

from internal.enrichment.type import EnricherConfig
from internal.runtime.type import OntologyConfig


def build_enricher_service(config: EnricherConfig) -> EnricherService:
    """
    Assemble EnricherService with lightweight providers.

    Priority order for entity resolution:
      1. Rule-based alias matching (AliasRegistry, loaded from ontology config)
      2. Embedding-based fallback (if embedding_model_id configured)
    
    Topic provider:
      - Phase 4: FallbackTopicProvider (keyword-based, no LLM)
      - Phase 5+: pluggable via config
    """
    alias_registry = _build_alias_registry()
    engine = CanonicalizationEngine(
        alias_registry=alias_registry,
        embedding_provider=None,     # no embedding at Phase 4 — plug in Phase 5+
        vector_index=None,
        fuzzy_threshold=0.85,
        embedding_threshold=0.82,
    )
    entity_enricher = EntityExtractionEnricher(engine=engine)

    semantic_enricher = SemanticInferenceEnricher(
        semantic_assist_enabled=False,           # disable LLM-assist at Phase 4
        semantic_hypothesis_rerank_enabled=False,
        semantic_corroboration_enabled=True,     # thread corroboration is pure-logic, keep
    )

    topic_enricher = TopicCandidateEnricher(
        topic_provider=FallbackTopicProvider(),  # keyword-based fallback
    )

    return EnricherService(
        entity_enricher=entity_enricher,
        topic_enricher=topic_enricher if config.topic_enabled else None,
        semantic_enricher=semantic_enricher if config.semantic_enabled else None,
    )


def _build_alias_registry() -> AliasRegistry:
    """
    Load alias registry from ontology config.
    Phase 4: empty registry — entities from UAP records only.
    Phase 5+: load from MinIO ontology bundle or Postgres ontology table.
    """
    return AliasRegistry(entities={}, aliases={})
```

## `helpers.py` — build MentionContext[]

```python
# internal/enrichment/usecase/helpers.py
# MentionContext is required by entity + semantic enrichers for thread-aware inference

from smap.normalization.models import MentionRecord
from smap.threads.models import MentionContext, ThreadBundle

def build_mention_contexts(
    mentions: list[MentionRecord],
    thread_bundle: ThreadBundle,
) -> list[MentionContext]:
    """
    Build MentionContext[] from ThreadBundle.
    MentionContext carries:
      - root_id, parent_id, lineage_ids (for inherited target resolution)
      - context_text (sibling/parent text, used by entity enricher for context span)
    """
    # index by root_id
    thread_map = {s.root_id: s for s in thread_bundle.summaries}
    edge_map: dict[str, list[str]] = {}   # parent_id → [child_ids]
    for edge in thread_bundle.edges:
        edge_map.setdefault(edge.parent_id, []).append(edge.child_id)

    mention_map = {m.mention_id: m for m in mentions}
    contexts = []
    for mention in mentions:
        root_id = mention.root_id or mention.mention_id
        lineage_ids = _build_lineage(mention.mention_id, mention.parent_id, mention_map)
        # context_text = root post text (if available)
        root_mention = mention_map.get(root_id)
        context_text = root_mention.clean_text if root_mention else ""

        contexts.append(MentionContext(
            mention_id=mention.mention_id,
            root_id=root_id,
            parent_id=mention.parent_id,
            lineage_ids=lineage_ids,
            context_text=context_text,
        ))
    return contexts


def _build_lineage(
    mention_id: str,
    parent_id: str | None,
    mention_map: dict[str, MentionRecord],
    max_depth: int = 5,
) -> list[str]:
    """Walk parent chain upward — returns [parent, grandparent, ...]."""
    lineage = []
    current = parent_id
    for _ in range(max_depth):
        if current is None or current == mention_id:
            break
        lineage.append(current)
        parent = mention_map.get(current)
        current = parent.parent_id if parent else None
    return lineage
```

## Key enrichers — porting notes

### `EntityExtractionEnricher`
**Source:** `core-analysis/src/smap/enrichers/entity.py`

Two-pass resolution:
1. `discoverer.discover()` — alias scan + NER providers → `EntityCandidate[]`
2. `engine.resolve()` → `EntityFact` with `resolution_kind` ∈ `{canonical_entity, concept, unresolved_candidate}`

**Phase 4 scope:**
- No LLM NER provider (`ner_provider_builder = lambda _: []`)
- Rule-based alias matching only (AliasRegistry from ontology)
- `annotate_batch_local_candidates()` — cluster unresolved mentions into `EntityCandidateClusterFact[]`

**What consumers get:**
- `entity_facts[].canonical_entity_id` → used for target-sentiment attribution
- `entity_facts[].entity_type` — brand/product/person/location
- `entity_candidate_clusters[]` — feeds into human-in-the-loop review (Phase 5+)

---

### `SemanticInferenceEnricher`
**Source:** `core-analysis/src/smap/enrichers/semantic.py`

**Phase 4 config (lightweight):**
```python
SemanticInferenceEnricher(
    ontology_registry=None,       # no ontology-conditioned ABSA at Phase 4
    prototype_registry=None,      # falls back to ASPECT_SEEDS / ISSUE_SEEDS hardcoded dicts
    taxonomy_mapping_provider=None,  # disables semantic_assist
    reranker_provider=None,
    embedding_provider=None,
    semantic_assist_enabled=False,
    semantic_hypothesis_rerank_enabled=False,
    semantic_corroboration_enabled=True,  # pure-logic, always on
)
```

**What ASPECT_SEEDS / ISSUE_SEEDS provide (from `enrichers/anchors.py`):**
- Lexical seed phrases for 12 aspect categories: `price`, `quality`, `performance`, `durability`, `availability`, `customer_service`, `delivery`, `trust`, `safety`, `battery`, `charging`, `usability`
- Issue categories: `pricing_value_concern`, `product_defect`, `performance_problem`, `availability_problem`, `service_problem`, `delivery_problem`, `trust_concern`, `safety_concern`, `usability_problem`

**Output facts (all in `EnrichmentBundle`):**
- `sentiment_facts[]` — `SentimentFact` (mention-level sentiment, score -1..+1)
- `target_sentiment_facts[]` — `TargetSentimentFact` (per entity-target)
- `aspect_opinion_facts[]` — `AspectOpinionFact`
- `issue_signal_facts[]` — `IssueSignalFact` (feeds `nlp.issues[]` in Layer 3 contract)
- `stance_facts[]` — `StanceFact` (feeds `nlp.stance` in Layer 3 contract)
- `intent_facts[]` — `IntentFact` (feeds `nlp.intent` in Layer 3 contract)

**Scoring fix for contract compliance:**
`SentimentFact.score` từ semantic enricher đã là -1..+1 (hỏi lại là `abs(total_score)` trong `_aggregate_mention_sentiment`). Kiểm tra trong `contract_publisher` nếu cần remap:
```python
# contract_publisher/usecase/build_layer3.py
# score field mapping: SentimentFact → InsightMessage.nlp.sentiment.score
sentiment_score = fact.score if fact.sentiment != "negative" else -abs(fact.score)
# NOTE: SentimentFact.score = abs(total_score) — always positive float
# Re-sign based on label for contract compliance (-1..+1)
```

---

### `TopicCandidateEnricher`
**Source:** `core-analysis/src/smap/enrichers/topic.py`

Two-pass:
1. `prepare()` — batch: embed documents, call `topic_provider.discover()`, build `TopicArtifactFact[]`
2. `enrich(mention, context)` — per-mention: return cached `TopicFact[]`

**Phase 4: `FallbackTopicProvider`**
- Keyword TF-IDF clustering, no embedding
- Lower quality artifacts (`quality_score` will be low, many `discovery_only`)
- Sufficient for end-to-end smoke testing

**Phase 5+:** Plug in FAISS-based or external topic provider via `EnricherConfig`

**Key output:**
- `topic_facts[]` — `TopicFact` (per-mention topic assignment with `reporting_topic_key`)
- `topic_artifacts[]` — `TopicArtifactFact` (per-topic quality scores, salient_terms, etc.)

## `interface.py`

```python
# internal/enrichment/interface.py
from abc import ABC, abstractmethod
from internal.enrichment.type import EnrichmentInput, EnrichmentOutput, EnricherConfig

class IEnrichmentUseCase(ABC):
    @abstractmethod
    def enrich(self, inp: EnrichmentInput, config: EnricherConfig) -> EnrichmentOutput:
        ...
```

## Libraries cần thêm vào `pyproject.toml`

```toml
dependencies = [
    # ... existing + Phase 3 deps ...
    "faiss-cpu>=1.7",            # vector index for entity resolution (Phase 5+)
    # sentence-transformers or equivalent: add when embedding provider plugged in Phase 5+
]
```

> **Note:** Phase 4 không cần `faiss-cpu` ngay — chỉ cần nếu embedding provider được plug in.
> Tuy nhiên thêm vào deps bây giờ để không bị thiếu khi deploy.

## Wiring trong `run_pipeline.py` (Phase 2 extension)

```python
# internal/pipeline/usecase/run_pipeline.py (cập nhật)
from internal.enrichment.usecase.enrich_batch import enrich_batch
from internal.enrichment.type import EnrichmentInput

# Sau stage threads (Phase 3):
if config.enrichment_enabled:
    enrichment_out = enrich_batch(
        EnrichmentInput(mentions=mentions, thread_bundle=thread_bundle),
        config=config.enricher_config,
    )
    enrichment_bundle = enrichment_out.bundle
else:
    enrichment_bundle = EnrichmentBundle()   # empty bundle — reports will be empty
```

## Gate Phase 4

- [ ] `EnricherService.enrich_mentions()` không raise exception trên 100 sample MentionRecords
- [ ] `SentimentFact[]` non-empty cho >= 80% mentions với Vietnamese text
- [ ] `EntityFact[]` có ít nhất 1 `unresolved_candidate` (alias scan working)
- [ ] `TopicFact[]` non-empty (FallbackTopicProvider returns at least 1 topic cluster)
- [ ] `IssueSignalFact[]` populated khi test với mentions chứa từ khóa issue seeds
- [ ] `EnrichmentBundle` pass `model_dump()` cleanly (no serialization error)
