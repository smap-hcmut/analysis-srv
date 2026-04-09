"""storage/constant.py — layer names and path conventions."""

from __future__ import annotations

# Bronze layer
BRONZE_RAW_JSONL = "uap_records.jsonl"

# Silver layer filenames
SILVER_MENTIONS = "mentions.parquet"
SILVER_DEDUP_CLUSTERS = "dedup_clusters.parquet"
SILVER_AUTHOR_QUALITY = "author_quality.parquet"
SILVER_THREAD_EDGES = "thread_edges.parquet"
SILVER_THREAD_CONTEXTS = "mention_contexts.parquet"
SILVER_THREAD_SUMMARIES = "thread_summaries.parquet"

# Gold layer filenames
GOLD_ENTITIES = "entity_facts.parquet"
GOLD_ENTITY_CANDIDATE_CLUSTERS = "entity_candidate_clusters.parquet"
GOLD_KEYWORDS = "keyword_facts.parquet"
GOLD_TOPICS = "topic_facts.parquet"
GOLD_SENTIMENT = "sentiment_facts.parquet"
GOLD_TARGET_SENTIMENT = "target_sentiment_facts.parquet"
GOLD_INTENTS = "intent_facts.parquet"
GOLD_ASPECTS = "aspect_facts.parquet"
GOLD_ISSUES = "issue_facts.parquet"

# Report filenames
METRICS_FILE = "metrics.json"
BI_REPORTS_FILE = "bi_reports.json"
RUN_MANIFEST_FILE = "run_manifest.json"
INSIGHTS_FILE = "insights.jsonl"

# Directory names
LAYER_BRONZE = "bronze"
LAYER_SILVER = "silver"
LAYER_GOLD = "gold"
LAYER_MARTS = "marts"
LAYER_REPORTS = "reports"
LAYER_INSIGHTS = "insights"

__all__ = [
    "BRONZE_RAW_JSONL",
    "SILVER_MENTIONS",
    "SILVER_DEDUP_CLUSTERS",
    "SILVER_AUTHOR_QUALITY",
    "SILVER_THREAD_EDGES",
    "SILVER_THREAD_CONTEXTS",
    "SILVER_THREAD_SUMMARIES",
    "GOLD_ENTITIES",
    "GOLD_ENTITY_CANDIDATE_CLUSTERS",
    "GOLD_KEYWORDS",
    "GOLD_TOPICS",
    "GOLD_SENTIMENT",
    "GOLD_TARGET_SENTIMENT",
    "GOLD_INTENTS",
    "GOLD_ASPECTS",
    "GOLD_ISSUES",
    "METRICS_FILE",
    "BI_REPORTS_FILE",
    "RUN_MANIFEST_FILE",
    "INSIGHTS_FILE",
    "LAYER_BRONZE",
    "LAYER_SILVER",
    "LAYER_GOLD",
    "LAYER_MARTS",
    "LAYER_REPORTS",
    "LAYER_INSIGHTS",
]
