"""build_layer1_payload.py — BIReportBundle → AnalyticsDigestMessage dict (Layer 1).

Layer 1 is a single aggregate dict summarising the top-level findings of a
pipeline run.  Consumed by downstream analytics dashboards.
"""

from __future__ import annotations

from internal.reporting.type import BIReportBundle
from internal.reporting.usecase.helpers import _top_n_rows, _window_to_str


def build_layer1_payload(
    run_id: str,
    project_id: str,
    campaign_id: str,
    reports: BIReportBundle,
) -> dict:
    """Return a single AnalyticsDigestMessage dict from a BIReportBundle.

    Structure
    ---------
    {
        "schema_version": "1.0",
        "run_id": ...,
        "project_id": ...,
        "campaign_id": ...,
        "analysis_window": { "start": ..., "end": ... },
        "mention_volume": <int>,
        "effective_mention_volume": <float>,
        "top_entities": [ { entity_name, mention_count, mention_share, ... }, ... ],
        "top_topics": [ { reporting_topic_label, mention_count, buzz_score_proxy, ... }, ... ],
        "top_issues": [ { issue_category, mention_count, issue_pressure_proxy, ... }, ... ],
    }
    """
    sov = reports.sov_report
    buzz = reports.buzz_report
    issues = reports.top_issues_report

    window = sov.window
    analysis_window = {
        "start": window.analysis_start,
        "end": window.analysis_end,
        "label": _window_to_str(window),
    }

    mention_volume = (
        sum(row.mention_count for row in sov.entities) + sov.unresolved_summary.count
    )
    effective_mention_volume = sov.effective_mention_volume

    top_entities = [
        {
            "canonical_entity_id": row.canonical_entity_id,
            "entity_name": row.entity_name,
            "entity_type": row.entity_type,
            "mention_count": row.mention_count,
            "mention_share": row.mention_share,
            "effective_mention_count": row.effective_mention_count,
            "effective_mention_share": row.effective_mention_share,
            "delta_mention_count": row.delta_mention_count,
        }
        for row in _top_n_rows(sov.entities, 10)
    ]

    top_topics = [
        {
            "reporting_topic_key": row.reporting_topic_key,
            "reporting_topic_label": row.reporting_topic_label,
            "mention_count": row.mention_count,
            "mention_share": row.mention_share,
            "buzz_score_proxy": row.buzz_score_proxy,
            "growth_ratio_proxy": row.growth_ratio_proxy,
            "reportability_score": row.reportability_score,
            "weak_topic": row.weak_topic,
            "noisy_topic": row.noisy_topic,
        }
        for row in _top_n_rows(buzz.topic_buzz, 10)
    ]

    top_issues = [
        {
            "issue_category": row.issue_category,
            "mention_count": row.mention_count,
            "issue_fact_count": row.issue_fact_count,
            "mention_prevalence_ratio": row.mention_prevalence_ratio,
            "issue_pressure_proxy": row.issue_pressure_proxy,
            "growth_delta_mentions": row.growth_delta_mentions,
        }
        for row in _top_n_rows(issues.issues, 10)
    ]

    return {
        "schema_version": "1.0",
        "run_id": run_id,
        "project_id": project_id,
        "campaign_id": campaign_id,
        "analysis_window": analysis_window,
        "mention_volume": mention_volume,
        "effective_mention_volume": effective_mention_volume,
        "top_entities": top_entities,
        "top_topics": top_topics,
        "top_issues": top_issues,
        "weighting_mode": sov.weighting_mode,
        "bi_schema_version": reports.bi_schema_version,
    }


__all__ = ["build_layer1_payload"]
