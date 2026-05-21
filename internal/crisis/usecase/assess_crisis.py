"""crisis/usecase/assess_crisis.py — rule-based 3-signal crisis scorer.

Project crisis config is wider than the current runtime scorer. The scorer is
intentionally limited to dashboard-grade BI signals that are already available
for every project:

- volume_trigger.rules[].threshold_percent_growth tunes the issue_pressure
  thresholds derived from top_issues_report.
- sentiment_trigger.rules[type=NEGATIVE_SPIKE].threshold_percent tunes the
  sentiment_collapse proxy derived from SOV entity deltas.
- influencer_trigger.rules[type=VIRAL_NEGATIVE].min_comments tunes the
  controversy_spike thresholds derived from thread_controversy_report.

keywords_trigger and the remaining subfields are stored for issue
classification, UI presets, and future crisis scorer expansion. They are not
direct CRISIS_ALERT gates in this runtime version.
"""

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
    crisis_config: dict | None = None,
) -> CrisisAssessment:
    """Rule-based crisis scoring — no ML.

    Evaluates three independent signals:
    1. Issue pressure (top issue from top_issues_report)
    2. Thread controversy spike (top thread from thread_controversy_report)
    3. Sentiment collapse (entity-level proxy from sov_report deltas)
    """
    signals: list[CrisisSignal] = []
    thresholds = _thresholds_from_config(crisis_config)

    # --- Signal 1: Issue pressure ---
    if reports.top_issues_report.issues:
        top_issue = reports.top_issues_report.issues[0]
        pressure = top_issue.issue_pressure_proxy
        if pressure >= thresholds["issue_watch"]:
            signals.append(
                CrisisSignal(
                    signal_type="issue_pressure",
                    severity=_pressure_to_severity(pressure, thresholds),
                    evidence_value=pressure,
                    threshold_used=thresholds["issue_watch"],
                    evidence_references=top_issue.evidence_references,
                )
            )

    # --- Signal 2: Thread controversy spike ---
    if reports.thread_controversy_report.threads:
        top_thread = reports.thread_controversy_report.threads[0]
        score = top_thread.controversy_score_proxy
        if score >= thresholds["controversy_watch"]:
            signals.append(
                CrisisSignal(
                    signal_type="controversy_spike",
                    severity=_controversy_to_severity(score, thresholds),
                    evidence_value=score,
                    threshold_used=thresholds["controversy_watch"],
                    evidence_references=top_thread.evidence_references,
                )
            )

    # --- Signal 3: Sentiment collapse proxy ---
    neg_count, total = _count_negative_entity_proxy(reports)
    if total > 0:
        neg_ratio = neg_count / total
        if neg_ratio >= thresholds["sentiment_watch"]:
            signals.append(
                CrisisSignal(
                    signal_type="sentiment_collapse",
                    severity=_neg_ratio_to_severity(neg_ratio, thresholds),
                    evidence_value=round(neg_ratio, 4),
                    threshold_used=thresholds["sentiment_watch"],
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


def _pressure_to_severity(pressure: float, thresholds: dict[str, float]) -> str:
    if pressure >= thresholds["issue_critical"]:
        return "critical_like_proxy"
    if pressure >= thresholds["issue_warning"]:
        return "high"
    return "medium"


def _controversy_to_severity(score: float, thresholds: dict[str, float]) -> str:
    if score >= thresholds["controversy_critical"]:
        return "critical_like_proxy"
    if score >= thresholds["controversy_warning"]:
        return "high"
    return "medium"


def _neg_ratio_to_severity(ratio: float, thresholds: dict[str, float]) -> str:
    if ratio >= thresholds["sentiment_critical"]:
        return "high"
    if ratio >= thresholds["sentiment_warning"]:
        return "medium"
    return "low"


def _thresholds_from_config(crisis_config: dict | None) -> dict[str, float]:
    thresholds = {
        "issue_watch": C.ISSUE_PRESSURE_WATCH,
        "issue_warning": C.ISSUE_PRESSURE_WARNING,
        "issue_critical": C.ISSUE_PRESSURE_CRITICAL,
        "controversy_watch": C.CONTROVERSY_WATCH,
        "controversy_warning": C.CONTROVERSY_WARNING,
        "controversy_critical": C.CONTROVERSY_CRITICAL,
        "sentiment_watch": C.SENTIMENT_COLLAPSE_WATCH,
        "sentiment_warning": C.SENTIMENT_COLLAPSE_WARNING,
        "sentiment_critical": C.SENTIMENT_COLLAPSE_CRITICAL,
    }
    if not isinstance(crisis_config, dict):
        return thresholds

    _apply_issue_pressure_thresholds(thresholds, crisis_config)
    _apply_sentiment_collapse_thresholds(thresholds, crisis_config)
    _apply_controversy_spike_thresholds(thresholds, crisis_config)

    return thresholds


def _apply_issue_pressure_thresholds(
    thresholds: dict[str, float],
    crisis_config: dict,
) -> None:
    """Map volume_trigger growth rules to BI issue_pressure thresholds.

    Runtime source: top_issues_report.issues[0].issue_pressure_proxy.
    Wired config: threshold_percent_growth only. Metric, comparison window,
    and baseline are reserved until historical baseline scoring is added.
    """
    volume = crisis_config.get("volume_trigger") or {}
    if isinstance(volume, dict) and volume.get("enabled", True):
        rules = volume.get("rules") or []
        for rule in rules:
            if not isinstance(rule, dict):
                continue
            level = str(rule.get("level") or "").upper()
            growth = _float(rule.get("threshold_percent_growth"), 0.0)
            if growth <= 0:
                continue
            pressure = max(1.0, growth / 15.0)
            if level == "WARNING":
                thresholds["issue_warning"] = pressure
                thresholds["issue_watch"] = min(thresholds["issue_watch"], pressure * 0.45)
            elif level == "CRITICAL":
                thresholds["issue_critical"] = pressure


def _apply_sentiment_collapse_thresholds(
    thresholds: dict[str, float],
    crisis_config: dict,
) -> None:
    """Map NEGATIVE_SPIKE threshold to the sentiment_collapse proxy.

    Runtime source: count of SOV entities where delta_mention_count < 0.
    Wired config: NEGATIVE_SPIKE.threshold_percent only. Min sample size,
    aspect lists, and ASPECT_NEGATIVE are reserved until mart-level sentiment
    joins are evaluated directly.
    """
    sentiment = crisis_config.get("sentiment_trigger") or {}
    if isinstance(sentiment, dict) and sentiment.get("enabled", True):
        rules = sentiment.get("rules") or []
        for rule in rules:
            if not isinstance(rule, dict):
                continue
            if str(rule.get("type") or "").upper() != "NEGATIVE_SPIKE":
                continue
            warning = _float(rule.get("threshold_percent"), 0.0) / 100.0
            if warning > 0:
                thresholds["sentiment_warning"] = min(max(warning, 0.05), 0.95)
                thresholds["sentiment_watch"] = min(
                    thresholds["sentiment_warning"] * 0.75,
                    thresholds["sentiment_warning"],
                )
                thresholds["sentiment_critical"] = min(
                    max(
                        thresholds["sentiment_warning"] * 1.5,
                        thresholds["sentiment_warning"],
                    ),
                    0.98,
                )
                break


def _apply_controversy_spike_thresholds(
    thresholds: dict[str, float],
    crisis_config: dict,
) -> None:
    """Map VIRAL_NEGATIVE comment threshold to controversy_spike thresholds.

    Runtime source: thread_controversy_report.threads[0].controversy_score_proxy.
    Wired config: VIRAL_NEGATIVE.min_comments only. HIGH_REACH, followers,
    shares, sentiment, and trigger logic are reserved until author/reach fields
    are joined into crisis scoring.
    """
    influencer = crisis_config.get("influencer_trigger") or {}
    if isinstance(influencer, dict) and influencer.get("enabled", True):
        rules = influencer.get("rules") or []
        viral_comments = [
            _float(rule.get("min_comments"), 0.0)
            for rule in rules
            if isinstance(rule, dict)
            if str(rule.get("type") or "").upper() == "VIRAL_NEGATIVE"
        ]
        if viral_comments:
            strictness = min(max(min(viral_comments) / 200.0, 0.6), 2.0)
            thresholds["controversy_watch"] = max(
                0.25,
                C.CONTROVERSY_WATCH * strictness,
            )
            thresholds["controversy_warning"] = max(
                thresholds["controversy_watch"],
                C.CONTROVERSY_WARNING * strictness,
            )
            thresholds["controversy_critical"] = max(
                thresholds["controversy_warning"],
                min(0.98, C.CONTROVERSY_CRITICAL * strictness),
            )


def _float(value: object, fallback: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback


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
