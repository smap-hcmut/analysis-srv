"""Build the analytics.batch.completed payload (Layer 3).

Topic: analytics.batch.completed
One message per run containing the full documents[] array.
"""

from internal.model.uap import UAPRecord
from internal.model.insight_message import InsightMessage
from internal.contract_publisher.type import RunContext
from .helpers import (
    normalize_platform_upper,
    detect_media_type,
    truncate_summary,
    normalize_sentiment_score,
)


def build_batch_completed_payload(
    pairs: list[tuple[UAPRecord, InsightMessage]],
    ctx: RunContext,
) -> dict:
    """Build the full analytics.batch.completed message.

    Args:
        pairs: List of (UAPRecord, InsightMessage) tuples from the buffer.
        ctx:   RunContext for this flush.

    Returns:
        Dict ready for JSON serialization.
    """
    documents = [
        _map_document(uap, msg) for uap, msg in pairs if _should_include(uap, msg)
    ]

    return {
        "project_id": ctx.project_id,
        "campaign_id": ctx.campaign_id,
        "documents": documents,
    }


def _should_include(uap: UAPRecord, msg: InsightMessage) -> bool:
    """Gate: only include documents with a non-empty uap_id and clean_text."""
    uap_id = msg.identity.doc_id if msg.identity else ""
    clean_text = msg.content.clean_text if msg.content else ""
    raw_text = msg.content.text if msg.content else ""
    return bool(uap_id and (clean_text or raw_text))


def _map_document(uap: UAPRecord, msg: InsightMessage) -> dict:
    """Map (UAPRecord, InsightMessage) → InsightMessage contract schema."""
    identity = msg.identity
    content = msg.content
    nlp = msg.nlp
    biz = msg.business

    # Derive uap_media_type from UAPRecord attachments (not in InsightMessage)
    media_type = detect_media_type(uap)

    # Sentiment score: re-sign to -1..+1 range
    label = nlp.sentiment.label if nlp and nlp.sentiment else "NEUTRAL"
    raw_score = nlp.sentiment.score if nlp and nlp.sentiment else 0.0
    signed_score = normalize_sentiment_score(label, raw_score)

    # Content
    clean_text = (content.clean_text or content.text) if content else ""
    summary = content.summary if content else ""
    if not summary:
        summary = truncate_summary(clean_text)

    # Aspects: keep only required fields
    aspects = []
    if nlp and nlp.aspects:
        for a in nlp.aspects:
            aspects.append(
                {
                    "aspect": (a.aspect or "").upper(),
                    "polarity": (a.polarity or "NEUTRAL").upper(),
                }
            )

    # Entities: keep only required fields
    entities = []
    if nlp and nlp.entities:
        for e in nlp.entities:
            if e.type and e.value:
                entities.append(
                    {
                        "type": (e.type or "OTHER").upper(),
                        "value": e.value,
                    }
                )

    # Engagement: rename like_count → likes, etc.
    engagement: dict = {"likes": 0, "comments": 0, "shares": 0, "views": 0}
    if biz and biz.impact and biz.impact.engagement:
        eng = biz.impact.engagement
        engagement = {
            "likes": eng.like_count,
            "comments": eng.comment_count,
            "shares": eng.share_count,
            "views": eng.view_count,
        }

    impact_score = biz.impact.impact_score if biz and biz.impact else 0.0
    priority = biz.impact.priority if biz and biz.impact else "LOW"

    # RAG gate: flatten object → bool
    rag_bool = bool(msg.rag.index.should_index) if msg.rag and msg.rag.index else False

    result: dict = {
        "identity": {
            "uap_id": identity.doc_id if identity else "",
            "uap_type": (identity.doc_type or "post").lower() if identity else "post",
            "uap_media_type": media_type,
            "platform": normalize_platform_upper(
                identity.source_type if identity else ""
            ),
            "published_at": identity.published_at or "" if identity else "",
        },
        "content": {
            "clean_text": clean_text,
            "summary": summary,
        },
        "nlp": {
            "sentiment": {
                "label": label.upper(),
                "score": round(signed_score, 6),
            },
            "aspects": aspects,
            "entities": entities,
        },
        "business": {
            "impact": {
                "engagement": engagement,
                "impact_score": round(impact_score, 4),
                "priority": priority.upper(),
            },
        },
        "rag": rag_bool,
    }

    # Optional fields [v1.2] — only add if present in InsightMessage
    # These are populated in Phase 4+ when core-analysis enrichers are ported
    # For now they remain absent (omitted per backward compat rules)

    return result


__all__ = ["build_batch_completed_payload"]
