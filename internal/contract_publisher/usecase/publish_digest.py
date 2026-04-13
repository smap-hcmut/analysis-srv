"""Build analytics.report.digest payload (Layer 1).

Topic: analytics.report.digest
One message per run. MUST be published LAST (knowledge-srv uses it as trigger).

Phase 1 builds a minimal digest from buffer metadata (total count only).
top_entities/top_topics/top_issues will be populated in Phase 5 when
BIReportBundle from core-analysis is available.
"""

from typing import Any, Optional

from internal.contract_publisher.type import RunContext


def build_report_digest_payload(
    ctx: RunContext,
    total_mentions: int,
    bi_report_bundle: Optional[Any] = None,  # BIReportBundle — Phase 5+
) -> dict:
    """Build analytics.report.digest message.

    Args:
        ctx:              RunContext for this flush.
        total_mentions:   Number of documents in this run.
        bi_report_bundle: BIReportBundle from core-analysis (Phase 5+).
                          When None, top_entities/topics/issues are empty arrays.

    Returns:
        Dict ready for JSON serialization.
    """
    top_entities: list[dict] = []
    top_topics: list[dict] = []
    top_issues: list[dict] = []

    if bi_report_bundle is not None:
        sov = getattr(bi_report_bundle, "sov_report", None)
        buzz = getattr(bi_report_bundle, "buzz_report", None)
        issues_report = getattr(bi_report_bundle, "top_issues_report", None)

        if sov:
            top_entities = [
                _map_entity_row(row)
                for row in (getattr(sov, "entities", []) or [])[:10]
            ]
        if buzz:
            top_topics = [
                _map_topic_row(row)
                for row in (getattr(buzz, "topic_buzz", []) or [])[:10]
            ]
        if issues_report:
            top_issues = [
                _map_issue_row(row)
                for row in (getattr(issues_report, "issues", []) or [])[:10]
            ]

    return {
        "project_id": ctx.project_id,
        "campaign_id": ctx.campaign_id,
        "run_id": ctx.run_id,
        "analysis_window_start": ctx.analysis_window_start,
        "analysis_window_end": ctx.analysis_window_end,
        "domain_overlay": ctx.domain_overlay,
        "platform": ctx.platform,
        "total_mentions": total_mentions,
        "top_entities": top_entities,
        "top_topics": top_topics,
        "top_issues": top_issues,
        "should_index": True,
    }


def _map_entity_row(row: Any) -> dict:
    """Map a SOVRow to the contract top_entities[] schema."""
    return {
        "canonical_entity_id": getattr(row, "canonical_entity_id", ""),
        "entity_name": getattr(row, "entity_name", ""),
        "entity_type": (getattr(row, "entity_type", "") or "").lower(),
        "mention_count": int(getattr(row, "mention_count", 0) or 0),
        "mention_share": float(getattr(row, "mention_share", 0.0) or 0.0),
    }


def _map_topic_row(row: Any) -> dict:
    """Map a BuzzTopicRow to the contract top_topics[] schema."""
    topic_label = getattr(row, "reporting_topic_label", "") or ""
    topic_key = getattr(row, "reporting_topic_key", None)
    if not topic_key and topic_label:
        topic_key = topic_label.lower().replace(" ", "_")

    result: dict = {
        "topic_key": topic_key or "",
        "topic_label": topic_label,
        "mention_count": int(getattr(row, "mention_count", 0) or 0),
        "mention_share": float(getattr(row, "mention_share", 0.0) or 0.0),
    }

    # Conditionally add optional fields
    buzz_score = getattr(row, "buzz_score_proxy", None)
    if buzz_score is not None:
        result["buzz_score_proxy"] = float(buzz_score)

    quality_score = getattr(row, "quality_score", None)
    if quality_score is not None:
        result["quality_score"] = float(quality_score)

    rep_texts = getattr(row, "representative_texts", None)
    if rep_texts:
        result["representative_texts"] = list(rep_texts)[:3]

    # [v1.2] optional
    eff_count = getattr(row, "effective_mention_count", None)
    if eff_count is not None:
        result["effective_mention_count"] = float(eff_count)

    growth = getattr(row, "growth_ratio_proxy", None)
    if growth is not None:
        result["growth_ratio_proxy"] = float(growth)

    salient = getattr(row, "salient_terms", None)
    if salient:
        result["salient_terms"] = list(salient)[:10]

    return result


def _map_issue_row(row: Any) -> dict:
    """Map a TopIssueRow to the contract top_issues[] schema."""
    result: dict = {
        "issue_category": getattr(row, "issue_category", ""),
        "mention_count": int(getattr(row, "mention_count", 0) or 0),
        "issue_pressure_proxy": float(getattr(row, "issue_pressure_proxy", 0.0) or 0.0),
    }

    severity_mix = getattr(row, "severity_mix", None)
    if severity_mix:
        result["severity_mix"] = dict(severity_mix)

    return result


__all__ = ["build_report_digest_payload"]
