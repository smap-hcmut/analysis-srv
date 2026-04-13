from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional


@dataclass
class OntologyConfig:
    """Minimal ontology overlay applied per domain/campaign."""

    domain_overlay: str = ""
    brand_names: list[str] = field(default_factory=list)
    topic_seeds: list[str] = field(default_factory=list)
    stop_entities: list[str] = field(default_factory=list)


@dataclass
class RunContext:
    """Runtime context for a single pipeline run (batch-level)."""

    run_id: str
    project_id: str
    analysis_window_start: Optional[datetime] = None
    analysis_window_end: Optional[datetime] = None
    ontology: OntologyConfig = field(default_factory=OntologyConfig)
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class EnumRegistry:
    """Maps for normalizing enum values across pipeline stages."""

    sentiment_labels: frozenset[str] = field(
        default_factory=lambda: frozenset({"POSITIVE", "NEGATIVE", "NEUTRAL", "MIXED"})
    )
    platform_upstream: dict[str, str] = field(
        default_factory=lambda: {
            "tiktok": "TIKTOK",
            "facebook": "FACEBOOK",
            "instagram": "INSTAGRAM",
            "youtube": "YOUTUBE",
        }
    )


__all__ = ["OntologyConfig", "RunContext", "EnumRegistry"]
