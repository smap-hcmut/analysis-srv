from dataclasses import dataclass, field
from typing import Any, Optional

from internal.model.uap import UAPRecord
from internal.model.insight_message import InsightMessage


@dataclass
class RunContext:
    """Context for a single analysis run. Shared across all 3 topics."""

    run_id: str  # "run-20260409T143022Z"
    project_id: str  # "proj_cleanser_01"
    campaign_id: str  # "camp_q1_2026" (empty string if unknown)
    platform: str  # "tiktok" — lowercase per contract Layer 1
    domain_overlay: str  # "domain-facial-cleanser-vn"
    analysis_window_start: str  # RFC3339 UTC, e.g. "2026-02-01T10:17:00Z"
    analysis_window_end: str  # RFC3339 UTC


@dataclass
class ContractPublishConfig:
    """Configuration for ContractPublisherUseCase."""

    batch_size: int = 100
    """Auto-flush after this many documents are buffered."""

    flush_interval_seconds: float = 30.0
    """Max seconds before auto-flush (not enforced in Phase 1, reserved)."""

    enabled: bool = True
    """Kill-switch. If False, publish_one() and flush() are no-ops."""

    domain_overlay: str = ""
    """Default domain slug sent in Layer 1 digest."""


@dataclass
class PublishInput:
    """Input for a single document going through the contract publisher."""

    uap_record: UAPRecord
    insight_message: InsightMessage
    insight_cards: list[Any] = field(default_factory=list)
    """InsightCard list — populated in Phase 4+; empty list is valid."""


@dataclass
class PublishOutput:
    success: bool = True
    error_message: Optional[str] = None
    documents_published: int = 0
    insights_published: int = 0


__all__ = [
    "RunContext",
    "ContractPublishConfig",
    "PublishInput",
    "PublishOutput",
]
