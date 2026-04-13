"""crisis/usecase/assess_crisis.py — rule-based 3-signal crisis scorer."""

from __future__ import annotations

from typing import TYPE_CHECKING

from internal.crisis import constant as C
from internal.crisis.type import CrisisAssessment, CrisisLevel, CrisisSignal

if TYPE_CHECKING:
    from internal.reporting.type import BIReportBundle


def assess_crisis(
    run_id: str,
    project_id: str,
    campaign_id: str,
    reports: "BIReportBundle",
) -> CrisisAssessment:
    """Rule-based crisis scoring — no ML.

    Evaluates three independent signals:
    1. Issue pressure (top issue from top_issues_report)
    2. Thread controversy spike (top thread from thread_controversy_report)
    3. Sentiment collapse (entity-level proxy from sov_report deltas)
    """
    signals: list[CrisisSignal] = []

    # --- Signal 1: Issue pressure ---
    if reports.top_issues_report.issues:
        top_issue = reports.top_issues_report.issues[0]
        pressure = top_issue.issue_pressure_proxy
        if pressure >= C.ISSUE_PRESSURE_WATCH:
            signals.append(
                CrisisSignal(
                    signal_type="issue_pressure",
                    severity=_pressure_to_severity(pressure),
                    evidence_value=pressure,
                    threshold_used=C.ISSUE_PRESSURE_WATCH,
                    evidence_references=top_issue.evidence_references,
                )
            )

    # --- Signal 2: Thread controversy spike ---
    if reports.thread_controversy_report.threads:
        top_thread = reports.thread_controversy_report.threads[0]
        score = top_thread.controversy_score_proxy
        if score >= C.CONTROVERSY_WATCH:
            signals.append(
                CrisisSignal(
                    signal_type="controversy_spike",
                    severity=_controversy_to_severity(score),
                    evidence_value=score,
                    threshold_used=C.CONTROVERSY_WATCH,
                    evidence_references=top_thread.evidence_references,
                )
            )

    # --- Signal 3: Sentiment collapse proxy ---
    neg_count, total = _count_negative_entity_proxy(reports)
    if total > 0:
        neg_ratio = neg_count / total
        if neg_ratio >= C.SENTIMENT_COLLAPSE_WATCH:
            signals.append(
                CrisisSignal(
                    signal_type="sentiment_collapse",
                    severity=_neg_ratio_to_severity(neg_ratio),
                    evidence_value=round(neg_ratio, 4),
                    threshold_used=C.SENTIMENT_COLLAPSE_WATCH,
                    evidence_references=[],
                )
            )

    composite = _composite_score(signals)
    level = _crisis_level(composite, signals)

    top_issue = (
        reports.top_issues_report.issues[0]
        if reports.top_issues_report.issues
        else None
    )
    top_thread = (
        reports.thread_controversy_report.threads[0]
        if reports.thread_controversy_report.threads
        else None
    )

    return CrisisAssessment(
        run_id=run_id,
        project_id=project_id,
        campaign_id=campaign_id,
        crisis_level=level,
        signals=signals,
        top_issue_category=top_issue.issue_category if top_issue else None,
        top_issue_pressure=top_issue.issue_pressure_proxy if top_issue else 0.0,
        top_controversy_score=(
            top_thread.controversy_score_proxy if top_thread else 0.0
        ),
        composite_crisis_score=composite,
    )


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _pressure_to_severity(pressure: float) -> str:
    if pressure >= C.ISSUE_PRESSURE_CRITICAL:
        return "critical_like_proxy"
    if pressure >= C.ISSUE_PRESSURE_WARNING:
        return "high"
    return "medium"


def _controversy_to_severity(score: float) -> str:
    if score >= C.CONTROVERSY_CRITICAL:
        return "critical_like_proxy"
    if score >= C.CONTROVERSY_WARNING:
        return "high"
    return "medium"


def _neg_ratio_to_severity(ratio: float) -> str:
    if ratio >= C.SENTIMENT_COLLAPSE_CRITICAL:
        return "high"
    if ratio >= C.SENTIMENT_COLLAPSE_WARNING:
        return "medium"
    return "low"


def _composite_score(signals: list[CrisisSignal]) -> float:
    return round(sum(C.SEVERITY_WEIGHT.get(s.severity, 1.0) for s in signals), 4)


def _crisis_level(composite: float, signals: list[CrisisSignal]) -> CrisisLevel:
    if any(s.severity == "critical_like_proxy" for s in signals) or composite >= 5.0:
        return "critical"
    if composite >= 2.5:
        return "warning"
    if composite >= 0.8:
        return "watch"
    return "none"


def _count_negative_entity_proxy(
    reports: "BIReportBundle",
) -> tuple[int, int]:
    """Proxy for negative sentiment: count entities with negative delta_mention_count.

    This is an approximation. Full implementation would join fact_sentiment
    from MartBundle directly, but BIReportBundle alone provides delta signals
    from SOV report as a proxy.
    """
    entities = reports.sov_report.entities
    if not entities:
        return 0, 0
    total = len(entities)
    negative_proxy = sum(1 for e in entities if e.delta_mention_count < 0)
    return negative_proxy, total


__all__ = ["assess_crisis"]
