"""crisis/type.py — CrisisSignal, CrisisAssessment, CrisisLevel."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

# CrisisLevel: escalating severity
CrisisLevel = Literal["none", "watch", "warning", "critical"]


@dataclass
class CrisisSignal:
    """A single evidence signal contributing to the crisis score."""

    signal_type: str  # "issue_pressure" | "controversy_spike" | "sentiment_collapse"
    severity: str  # "low" | "medium" | "high" | "critical_like_proxy"
    evidence_value: float  # the raw measured value (pressure score, etc.)
    threshold_used: float  # which threshold triggered this signal
    evidence_references: list[str] = field(default_factory=list)  # mention_ids


@dataclass
class CrisisAssessment:
    """Aggregated crisis assessment for a pipeline run."""

    run_id: str
    project_id: str
    campaign_id: str
    crisis_level: CrisisLevel
    signals: list[CrisisSignal] = field(default_factory=list)
    top_issue_category: str | None = None
    top_issue_pressure: float = 0.0
    top_controversy_score: float = 0.0
    composite_crisis_score: float = 0.0

    def is_actionable(self) -> bool:
        """Return True if crisis level requires attention (watch or above)."""
        return self.crisis_level != "none"


@dataclass
class CrisisInput:
    """Input to the crisis usecase."""

    run_id: str
    project_id: str
    campaign_id: str
    bi_reports: object  # BIReportBundle


@dataclass
class CrisisOutput:
    """Output of the crisis usecase."""

    assessment: CrisisAssessment


__all__ = [
    "CrisisLevel",
    "CrisisSignal",
    "CrisisAssessment",
    "CrisisInput",
    "CrisisOutput",
]
