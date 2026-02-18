import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Union

from internal.post_insight.type import CreatePostInsightInput, UpdatePostInsightInput


def transform_to_post_insight(
    data: Union[CreatePostInsightInput, UpdatePostInsightInput, Dict[str, Any]],
) -> Dict[str, Any]:
    # Normalize to dict
    if hasattr(data, "to_dict"):
        data = data.to_dict()

    if not isinstance(data, dict):
        raise ValueError("Data must be a dict or have to_dict() method")

    if "project_id" not in data and "id" in data:
        return data
    now = datetime.now(timezone.utc)

    uap_metadata = _build_uap_metadata(data)

    aspects = _extract_aspects(data.get("aspects_breakdown", {}))

    risk_level = data.get("risk_level", "LOW")
    risk_score = _risk_level_to_score(risk_level)

    primary_intent = data.get("primary_intent", "DISCUSSION")

    is_spam_from_intent = primary_intent in ("SPAM", "SEEDING")
    is_spam_from_detection = data.get("is_spam", False)
    is_spam = is_spam_from_intent or is_spam_from_detection

    requires_attention = risk_level in ("HIGH", "CRITICAL")

    return {
        "id": _get_or_generate_id(data),
        "project_id": data.get("project_id", ""),
        "source_id": data.get("source_id"),  # Now available
        "content": data.get("content_text", ""),
        "content_created_at": _parse_datetime(data.get("published_at")),
        "ingested_at": _parse_datetime(data.get("crawled_at")),
        "platform": (data.get("platform") or "UNKNOWN").lower(),
        "uap_metadata": uap_metadata,
        "overall_sentiment": data.get("overall_sentiment", "NEUTRAL"),
        "overall_sentiment_score": data.get("overall_sentiment_score", 0.0),
        "sentiment_confidence": data.get("overall_confidence", 0.0),
        "sentiment_explanation": None,  # Phase 4
        "aspects": aspects,
        "keywords": data.get("keywords", []),
        "risk_level": risk_level,
        "risk_score": risk_score,
        "risk_factors": data.get("risk_factors", []),
        "requires_attention": requires_attention,
        "alert_triggered": False,
        "engagement_score": data.get("engagement_score", 0.0),
        "virality_score": data.get("virality_score", 0.0),
        "influence_score": data.get("influence_score", 0.0),
        "reach_estimate": data.get("view_count", 0),
        "content_quality_score": 0.0,
        "is_spam": is_spam,
        "is_bot": False,
        "language": None,
        "language_confidence": 0.0,
        "toxicity_score": 0.0,
        "is_toxic": False,
        "primary_intent": primary_intent,
        "intent_confidence": data.get("intent_confidence", 0.0),
        "impact_score": data.get("impact_score", 0.0),
        "processing_time_ms": data.get("processing_time_ms", 0),
        "model_version": data.get("model_version", "1.0.0"),
        "processing_status": data.get("processing_status", "success"),
        "analyzed_at": _parse_datetime(data.get("analyzed_at")) or now,
        "indexed_at": None,
        "created_at": now,
        "updated_at": now,
    }


def _get_or_generate_id(data: Dict[str, Any]) -> uuid.UUID:
    existing_id = data.get("id")
    if existing_id:
        if isinstance(existing_id, uuid.UUID):
            return existing_id
        try:
            return uuid.UUID(str(existing_id))
        except (ValueError, AttributeError):
            pass
    return uuid.uuid4()


def _build_uap_metadata(data: Dict[str, Any]) -> Dict[str, Any]:
    metadata: Dict[str, Any] = {}

    # Author fields
    author_fields = {
        "author": "author_id",
        "author_display_name": "author_name",
        "author_username": "author_username",
        "author_followers": "follower_count",
        "author_is_verified": "author_is_verified",
    }
    for meta_key, data_key in author_fields.items():
        if val := data.get(data_key):
            metadata[meta_key] = val

    # Engagement
    engagement = {
        k: data[f]
        for k, f in [
            ("views", "view_count"),
            ("likes", "like_count"),
            ("comments", "comment_count"),
            ("shares", "share_count"),
            ("saves", "save_count"),
        ]
        if (val := data.get(f)) is not None
    }
    if engagement:
        metadata["engagement"] = engagement

    for meta_key, data_key in [
        ("url", "permalink"),
        ("hashtags", "hashtags"),
    ]:
        if val := data.get(data_key):
            metadata[meta_key] = val

    return metadata


def _extract_aspects(aspects_breakdown: Any) -> list:
    if not isinstance(aspects_breakdown, dict):
        return []
    aspects = aspects_breakdown.get("aspects", [])
    if not isinstance(aspects, list):
        return []
    return [a for a in aspects if isinstance(a, dict)]


def _risk_level_to_score(risk_level: str) -> float:
    mapping = {
        "CRITICAL": 0.9,
        "HIGH": 0.7,
        "MEDIUM": 0.4,
        "LOW": 0.1,
    }
    return mapping.get(risk_level, 0.1)


def _parse_datetime(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            return None
    return None


__all__ = [
    "transform_to_post_insight",
]
