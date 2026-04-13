"""enrich_batch — top-level batch enrichment function.

Self-contained: no external smap.* imports.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from internal.enrichment.type import (
    EnricherConfig,
    EnrichmentInput,
    EnrichmentOutput,
)
from internal.enrichment.usecase.build_enricher_service import EnricherService
from internal.enrichment.usecase.helpers import build_mention_contexts

if TYPE_CHECKING:
    from internal.ontology.usecase.file_registry import FileOntologyRegistry

ENRICHER_VERSIONS: dict[str, str] = {
    "entity": "entity-simplified-v1",
    "semantic": "semantic-local-simplified-v1",
    "topic": "topic-simplified-v1",
    "keyword": "keyword-rules-v1",
    "stance": "stance-rules-v1",
    "intent": "intent-rules-v1",
    "source_influence": "source-influence-v1",
}


def enrich_batch(
    inp: EnrichmentInput,
    config: EnricherConfig,
    ontology_registry: "FileOntologyRegistry | None" = None,
) -> EnrichmentOutput:
    """Run enrichment on a batch of mentions.

    Args:
        inp: EnrichmentInput with mentions and optional thread_bundle
        config: EnricherConfig feature flags (entity/semantic/topic enabled)
        ontology_registry: Optional ontology registry for entity/aspect/issue/topic matching

    Returns:
        EnrichmentOutput with populated EnrichmentBundle
    """
    svc = EnricherService(ontology_registry=ontology_registry)
    contexts = build_mention_contexts(inp.mentions, inp.thread_bundle)
    bundle = svc.enrich_mentions(inp.mentions, contexts)
    return EnrichmentOutput(bundle=bundle, enricher_versions=ENRICHER_VERSIONS)
