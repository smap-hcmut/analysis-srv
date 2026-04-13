"""build_layer2_payload.py — BIReportBundle → list[InsightMessage dict] (Layer 2).

Layer 2 produces one dict per InsightCard in the bundle.  Each dict maps
directly to the InsightMessage schema consumed by downstream consumers.
"""

from __future__ import annotations

from internal.reporting.type import BIReportBundle
from internal.reporting.usecase.helpers import _window_to_str


def build_layer2_payloads(
    run_id: str,
    project_id: str,
    campaign_id: str,
    reports: BIReportBundle,
) -> list[dict]:
    """Return one InsightMessage dict per InsightCard in the bundle.

    Structure per item
    ------------------
    {
        "schema_version": "1.0",
        "run_id": ...,
        "project_id": ...,
        "campaign_id": ...,
        "insight_type": ...,
        "title": ...,
        "summary": ...,
        "confidence": ...,
        "time_window": ...,
        "supporting_metrics": { ... },
        "evidence_references": [ ... ],
        "source_reports": [ ... ],
        "filters_used": { ... },
    }
    """
    bundle = reports.insight_card_bundle
    window_label = _window_to_str(bundle.window)

    payloads = []
    for card in bundle.cards:
        payloads.append(
            {
                "schema_version": "1.0",
                "run_id": run_id,
                "project_id": project_id,
                "campaign_id": campaign_id,
                "insight_type": card.insight_type,
                "title": card.title,
                "summary": card.summary,
                "confidence": card.confidence,
                "time_window": card.time_window or window_label,
                "supporting_metrics": card.supporting_metrics,
                "evidence_references": card.evidence_references,
                "source_reports": card.source_reports,
                "filters_used": card.filters_used,
            }
        )

    return payloads


__all__ = ["build_layer2_payloads"]
