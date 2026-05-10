import uuid
from datetime import datetime, timezone
import math
import re
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

    content = data.get("content_text", "") or ""

    return {
        "id": _get_or_generate_id(data),
        "project_id": data.get("project_id", ""),
        "source_id": data.get("source_id"),  # Now available
        "content": content,
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
        "content_quality_score": _content_quality_score(data),
        "business_relevance_score": _business_relevance_score(data),
        "is_spam": is_spam,
        "is_bot": False,
        "language": data.get("language") or _guess_language(content),
        "language_confidence": data.get("language_confidence", 0.65 if content else 0.0),
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
        "author_avatar": "author_avatar_url",
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
        ("permalink", "permalink"),
        ("original_url", "permalink"),
        ("source_url", "permalink"),
        ("web_url", "permalink"),
        ("hashtags", "hashtags"),
    ]:
        if val := data.get(data_key):
            metadata[meta_key] = val

    enrichment_summary = data.get("enrichment_summary")
    if enrichment_summary:
        metadata["enrichment"] = enrichment_summary
    raw_context = data.get("raw_context")
    if isinstance(raw_context, dict):
        for key in ("platform_meta", "hierarchy", "domain_type_code", "crawl_keyword", "doc_type"):
            if val := raw_context.get(key):
                metadata[key] = val
        if doc_type := raw_context.get("doc_type"):
            metadata["content_type"] = doc_type
        hierarchy = raw_context.get("hierarchy")
        if isinstance(hierarchy, dict):
            if root_id := hierarchy.get("root_id"):
                metadata["root_id"] = root_id
            if parent_id := hierarchy.get("parent_id"):
                metadata["parent_id"] = parent_id
        parent_url = _extract_parent_post_url(raw_context)
        if parent_url:
            metadata["parent_post_url"] = parent_url
            if str(raw_context.get("doc_type") or "").lower() == "comment":
                metadata["comment_url"] = data.get("permalink") or parent_url
    if val := data.get("business_relevance_score"):
        metadata["business_relevance_score"] = val
    if val := data.get("business_relevance_reasons"):
        metadata["business_relevance_reasons"] = val

    return metadata


def _extract_parent_post_url(raw_context: Dict[str, Any]) -> str:
    platform_meta = raw_context.get("platform_meta")
    if not isinstance(platform_meta, dict):
        return ""
    youtube_meta = platform_meta.get("youtube")
    if isinstance(youtube_meta, dict):
        parent_url = youtube_meta.get("parent_url")
        if isinstance(parent_url, str) and parent_url.startswith(("http://", "https://")):
            return parent_url
        video_id = youtube_meta.get("parent_video_id")
        if isinstance(video_id, str) and video_id:
            return f"https://www.youtube.com/watch?v={video_id}"
    return ""


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


def _content_quality_score(data: Dict[str, Any]) -> float:
    explicit = data.get("content_quality_score")
    if isinstance(explicit, (int, float)) and explicit > 0:
        return _clamp(float(explicit))

    content = str(data.get("content_text") or "")
    compact = re.sub(r"\s+", " ", content).strip()
    if not compact:
        return 0.0

    primary_intent = str(data.get("primary_intent") or "").upper()
    if data.get("is_spam") or primary_intent in {"SPAM", "SEEDING"}:
        return 0.05

    words = re.findall(r"[\wÀ-ỹ]+", compact.lower(), flags=re.UNICODE)
    word_count = len(words)
    if word_count == 0:
        return 0.0

    unique_ratio = len(set(words)) / max(word_count, 1)
    length_score = min(len(compact) / 180.0, 1.0)
    lexical_score = min(max(unique_ratio, 0.0), 1.0)

    keywords = data.get("keywords") or []
    keyword_score = min(len(keywords) * 0.035, 0.18) if isinstance(keywords, list) else 0.0

    aspects = _extract_aspects(data.get("aspects_breakdown", {}))
    aspect_score = 0.16 if aspects else 0.0

    engagement_total = sum(
        int(data.get(key) or 0)
        for key in ("view_count", "like_count", "comment_count", "share_count", "save_count")
    )
    engagement_score = min(math.log10(engagement_total + 1) / 5.0, 1.0) * 0.12

    intent_bonus = 0.0
    if primary_intent in {"COMPLAINT", "CRISIS", "SUPPORT", "LEAD"}:
        intent_bonus = 0.08

    score = (
        0.12
        + length_score * 0.34
        + lexical_score * 0.18
        + keyword_score
        + aspect_score
        + engagement_score
        + intent_bonus
    )

    if len(compact) < 20:
        score *= 0.35
    elif len(compact) < 40:
        score *= 0.65

    return round(_clamp(score), 4)


def _business_relevance_score(data: Dict[str, Any]) -> float:
    explicit = data.get("business_relevance_score")
    if isinstance(explicit, (int, float)):
        return round(_clamp(float(explicit)), 4)
    return 0.0


def _guess_language(content: str) -> str | None:
    if not content:
        return None
    if re.search(r"[ăâđêôơưáàảãạấầẩẫậắằẳẵặéèẻẽẹếềểễệíìỉĩịóòỏõọốồổỗộớờởỡợúùủũụứừửữựýỳỷỹỵ]", content, re.IGNORECASE):
        return "vi"
    return "unknown"


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


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
