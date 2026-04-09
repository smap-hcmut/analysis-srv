"""enrich_batch — top-level batch enrichment function.

Self-contained: no external smap.* imports.
"""

from __future__ import annotations

from internal.enrichment.type import (
    EnricherConfig,
    EnrichmentInput,
    EnrichmentOutput,
)
from internal.enrichment.usecase.build_enricher_service import EnricherService
from internal.enrichment.usecase.helpers import build_mention_contexts

ENRICHER_VERSIONS: dict[str, str] = {
    "entity": "entity-simplified-v1",
    "semantic": "semantic-local-simplified-v1",
    "topic": "topic-simplified-v1",
    "keyword": "keyword-rules-v1",
    "stance": "stance-rules-v1",
    "intent": "intent-rules-v1",
    "source_influence": "source-influence-v1",
}


def enrich_batch(inp: EnrichmentInput, config: EnricherConfig) -> EnrichmentOutput:
    """Run enrichment on a batch of mentions.

    Args:
        inp: EnrichmentInput with mentions and optional thread_bundle
        config: EnricherConfig feature flags (entity/semantic/topic enabled)

    Returns:
        EnrichmentOutput with populated EnrichmentBundle
    """
    svc = EnricherService()
    contexts = build_mention_contexts(inp.mentions, inp.thread_bundle)
    bundle = svc.enrich_mentions(inp.mentions, contexts)
    return EnrichmentOutput(bundle=bundle, enricher_versions=ENRICHER_VERSIONS)
