"""Build analytics.insights.published payloads (Layer 2).

Topic: analytics.insights.published
One Kafka message per InsightCard. 5-15 messages per run.

For Phase 1: InsightCards come from Phase 4+ (core-analysis porting).
This module is wired but receives an empty list until Phase 4 is done.
"""

from typing import Any

from internal.contract_publisher.type import RunContext


def build_insights_published_payloads(
    cards: list[Any],  # list[InsightCard] — type Any until Phase 4 defines it
    ctx: RunContext,
) -> list[dict]:
    """Build one Kafka message dict per InsightCard.

    Args:
        cards: InsightCard list. Empty list is valid (Phase 1 produces nothing).
        ctx:   RunContext for this flush.

    Returns:
        List of dicts, each ready for JSON serialization. May be empty.
    """
    return [_map_card(card, ctx) for card in cards if _is_publishable(card)]


def _is_publishable(card: Any) -> bool:
    """Gate: skip cards with missing title/summary or very low confidence."""
    if not card:
        return False
    title = getattr(card, "title", None) or ""
    summary = getattr(card, "summary", None) or ""
    confidence = getattr(card, "confidence", 0.0) or 0.0
    return bool(title and summary and confidence >= 0.3)


def _map_card(card: Any, ctx: RunContext) -> dict:
    """Map an InsightCard to the contract schema."""
    time_window = getattr(card, "time_window", None) or ""
    window_start, window_end = _parse_time_window(time_window)
    supporting_metrics = getattr(card, "supporting_metrics", {}) or {}
    evidence_refs = getattr(card, "evidence_references", []) or []
    confidence = float(getattr(card, "confidence", 0.0) or 0.0)

    result: dict = {
        "project_id": ctx.project_id,
        "campaign_id": ctx.campaign_id,
        "run_id": ctx.run_id,
        "insight_type": getattr(card, "insight_type", ""),
        "title": getattr(card, "title", ""),
        "summary": getattr(card, "summary", ""),
        "confidence": round(confidence, 6),
        "analysis_window_start": window_start or ctx.analysis_window_start,
        "analysis_window_end": window_end or ctx.analysis_window_end,
        "supporting_metrics": dict(supporting_metrics),
        "evidence_references": list(evidence_refs),
        "should_index": bool(
            getattr(card, "title", "")
            and getattr(card, "summary", "")
            and confidence >= 0.3
        ),
    }

    # Optional [v1.2] fields from BuzzTopicRow — present only if in supporting_metrics
    if supporting_metrics.get("reportability_score") is not None:
        result["reportability_score"] = supporting_metrics["reportability_score"]
    if supporting_metrics.get("usefulness_score") is not None:
        result["usefulness_score"] = supporting_metrics["usefulness_score"]

    return result


def _parse_time_window(time_window: str) -> tuple[str | None, str | None]:
    """Parse "2026-01-01T00:00:00 to 2026-03-31T23:59:59" into (start, end).

    Returns (None, None) if the format is not recognized.
    """
    if not time_window or " to " not in time_window:
        return None, None

    parts = time_window.split(" to ", 1)
    start = _ensure_z(parts[0].strip())
    end = _ensure_z(parts[1].strip())
    return start, end


def _ensure_z(ts: str) -> str:
    """Ensure timestamp ends with Z (UTC marker)."""
    ts = ts.replace(" ", "T")
    if not ts.endswith("Z"):
        ts = ts + "Z"
    return ts


__all__ = ["build_insights_published_payloads"]
