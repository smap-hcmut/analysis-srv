"""Enrichment constants."""

from __future__ import annotations

ENRICHER_VERSIONS: dict[str, str] = {
    "entity": "entity-simplified-v1",
    "keyword": "keyword-rules-v1",
    "stance": "stance-rules-v1",
    "intent": "intent-rules-v1",
    "source_influence": "source-influence-v1",
    "semantic": "semantic-local-simplified-v1",
    "topic": "fallback-tfidf-v1",
}

ENRICHMENT_PROVIDER_VERSION = "enrichment-pipeline-v1"
