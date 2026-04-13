"""storage/type.py — StorageLayout: per-run directory layout."""

from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path

from internal.storage.constant import (
    BRONZE_RAW_JSONL,
    SILVER_MENTIONS,
    SILVER_DEDUP_CLUSTERS,
    SILVER_AUTHOR_QUALITY,
    SILVER_THREAD_EDGES,
    SILVER_THREAD_CONTEXTS,
    SILVER_THREAD_SUMMARIES,
    GOLD_ENTITIES,
    GOLD_ENTITY_CANDIDATE_CLUSTERS,
    GOLD_KEYWORDS,
    GOLD_TOPICS,
    GOLD_SENTIMENT,
    GOLD_TARGET_SENTIMENT,
    GOLD_INTENTS,
    GOLD_ASPECTS,
    GOLD_ISSUES,
    METRICS_FILE,
    BI_REPORTS_FILE,
    RUN_MANIFEST_FILE,
    INSIGHTS_FILE,
    LAYER_BRONZE,
    LAYER_SILVER,
    LAYER_GOLD,
    LAYER_MARTS,
    LAYER_REPORTS,
    LAYER_INSIGHTS,
)


@dataclass(frozen=True, slots=True)
class StorageLayout:
    """Per-run directory layout for analysis-srv.

    Paths are derived from a base_dir + run_id, creating a clean
    bronze/silver/gold/reports hierarchy per pipeline run.
    """

    base_dir: Path
    run_id: str

    @property
    def bronze_dir(self) -> Path:
        return self.base_dir / self.run_id / LAYER_BRONZE

    @property
    def silver_dir(self) -> Path:
        return self.base_dir / self.run_id / LAYER_SILVER

    @property
    def gold_dir(self) -> Path:
        return self.base_dir / self.run_id / LAYER_GOLD

    @property
    def marts_dir(self) -> Path:
        return self.gold_dir / LAYER_MARTS

    @property
    def reports_dir(self) -> Path:
        return self.base_dir / self.run_id / LAYER_REPORTS

    @property
    def insights_dir(self) -> Path:
        return self.base_dir / self.run_id / LAYER_INSIGHTS

    # ----- bronze -----

    @property
    def bronze_raw_jsonl(self) -> Path:
        return self.bronze_dir / BRONZE_RAW_JSONL

    # ----- silver -----

    @property
    def silver_mentions(self) -> Path:
        return self.silver_dir / SILVER_MENTIONS

    @property
    def silver_dedup_clusters(self) -> Path:
        return self.silver_dir / SILVER_DEDUP_CLUSTERS

    @property
    def silver_author_quality(self) -> Path:
        return self.silver_dir / SILVER_AUTHOR_QUALITY

    @property
    def silver_thread_edges(self) -> Path:
        return self.silver_dir / SILVER_THREAD_EDGES

    @property
    def silver_thread_contexts(self) -> Path:
        return self.silver_dir / SILVER_THREAD_CONTEXTS

    @property
    def silver_thread_summaries(self) -> Path:
        return self.silver_dir / SILVER_THREAD_SUMMARIES

    # ----- gold -----

    @property
    def gold_entities(self) -> Path:
        return self.gold_dir / GOLD_ENTITIES

    @property
    def gold_entity_candidate_clusters(self) -> Path:
        return self.gold_dir / GOLD_ENTITY_CANDIDATE_CLUSTERS

    @property
    def gold_keywords(self) -> Path:
        return self.gold_dir / GOLD_KEYWORDS

    @property
    def gold_topics(self) -> Path:
        return self.gold_dir / GOLD_TOPICS

    @property
    def gold_sentiment(self) -> Path:
        return self.gold_dir / GOLD_SENTIMENT

    @property
    def gold_target_sentiment(self) -> Path:
        return self.gold_dir / GOLD_TARGET_SENTIMENT

    @property
    def gold_intents(self) -> Path:
        return self.gold_dir / GOLD_INTENTS

    @property
    def gold_aspects(self) -> Path:
        return self.gold_dir / GOLD_ASPECTS

    @property
    def gold_issues(self) -> Path:
        return self.gold_dir / GOLD_ISSUES

    # ----- reports -----

    @property
    def metrics_file(self) -> Path:
        return self.reports_dir / METRICS_FILE

    @property
    def bi_reports_file(self) -> Path:
        return self.reports_dir / BI_REPORTS_FILE

    @property
    def run_manifest_file(self) -> Path:
        return self.reports_dir / RUN_MANIFEST_FILE

    @property
    def insights_file(self) -> Path:
        return self.insights_dir / INSIGHTS_FILE

    def ensure_directories(self) -> None:
        """Create all layer directories (idempotent)."""
        for d in (
            self.bronze_dir,
            self.silver_dir,
            self.gold_dir,
            self.marts_dir,
            self.reports_dir,
            self.insights_dir,
        ):
            d.mkdir(parents=True, exist_ok=True)

    @classmethod
    def for_run(cls, run_id: str, base_dir: Path | None = None) -> "StorageLayout":
        """Create a StorageLayout rooted at base_dir (default: system tmp)."""
        if base_dir is None:
            base_dir = Path(tempfile.gettempdir()) / "analysis-srv"
        return cls(base_dir=base_dir, run_id=run_id)


__all__ = ["StorageLayout"]
