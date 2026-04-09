"""Reporting module constants."""

from __future__ import annotations

BI_SCHEMA_VERSION = "2026.03.20-analysis-r1"

MART_TABLE_NAMES = [
    "fact_mentions",
    "fact_entity_mentions",
    "fact_entity_candidate_clusters",
    "fact_threads",
    "fact_dedup_clusters",
    "fact_topics",
    "fact_topic_artifacts",
    "fact_aspects",
    "fact_sentiment",
    "fact_target_sentiment",
    "fact_intents",
    "fact_issue_signals",
    "fact_author_quality",
    "dim_entities",
    "dim_taxonomy",
    "dim_sources",
    "dim_projects",
    "dim_time",
]

__all__ = ["BI_SCHEMA_VERSION", "MART_TABLE_NAMES"]
