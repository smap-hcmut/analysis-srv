"""Build the analytics.batch.completed payload (Layer 3).

Topic: analytics.batch.completed
One message per run containing the full documents[] array.
"""

from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from internal.contract_publisher.type import RunContext
from internal.model.insight_message import InsightMessage
from internal.model.uap import UAPRecord

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
    context_summary = content.context_summary if content else ""
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
            "context_summary": context_summary,
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
            "relevance_score": round(biz.relevance_score, 4) if biz else 0.0,
            "relevance_reasons": biz.relevance_reasons if biz else [],
            "impact": {
                "engagement": engagement,
                "impact_score": round(impact_score, 4),
                "priority": priority.upper(),
            },
        },
        "rag": rag_bool,
    }

    source = _map_source(uap)
    if source:
        result["source"] = source

    return result


def _map_source(uap: UAPRecord) -> dict[str, Any]:
    content = uap.content
    raw = uap.raw if isinstance(uap.raw, dict) else {}
    hierarchy = raw.get("hierarchy") if isinstance(raw.get("hierarchy"), dict) else {}
    platform_meta = (
        raw.get("platform_meta") if isinstance(raw.get("platform_meta"), dict) else {}
    )

    original_url = _resolve_original_url(uap)
    parent_post_url = _platform_parent_url(uap, platform_meta, hierarchy)
    source: dict[str, Any] = {
        "url": content.url if content and _is_http_url(content.url) else "",
        "original_url": original_url,
        "permalink": original_url,
        "source_url": original_url,
        "web_url": original_url,
        "parent_post_url": parent_post_url,
        "content_type": (content.doc_type or "").lower() if content else "",
        "root_id": str(hierarchy.get("root_id") or ""),
        "parent_id": str(hierarchy.get("parent_id") or ""),
        "platform_meta": platform_meta,
        "hierarchy": hierarchy,
    }
    if content and (content.doc_type or "").lower() == "comment":
        source["comment_url"] = original_url

    if content and content.author:
        source.update(
            {
                "author": content.author.author_id or "",
                "author_display_name": content.author.display_name or "",
                "author_username": content.author.username or "",
                "author_avatar": content.author.avatar_url or "",
            }
        )

    return {k: v for k, v in source.items() if v not in ("", None, {}, [])}


def _is_http_url(value: Any) -> bool:
    return isinstance(value, str) and (
        value.startswith("https://") or value.startswith("http://")
    )


def _with_query_param(url: str, key: str, value: str) -> str:
    parsed = urlparse(url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query[key] = value
    return urlunparse(parsed._replace(query=urlencode(query)))


def _platform_parent_url(
    uap: UAPRecord,
    platform_meta: dict[str, Any],
    hierarchy: dict[str, Any],
) -> str:
    platform = ""
    if uap.ingest and uap.ingest.source:
        platform = str(uap.ingest.source.source_type or "").strip().lower()

    if platform == "youtube":
        youtube_meta = (
            platform_meta.get("youtube")
            if isinstance(platform_meta.get("youtube"), dict)
            else {}
        )
        parent_url = str(youtube_meta.get("parent_url") or "").strip()
        video_id = str(youtube_meta.get("parent_video_id") or "").strip()
        root_id = str(hierarchy.get("root_id") or "").strip()
        if not video_id and root_id.startswith("yt_p_"):
            video_id = root_id.removeprefix("yt_p_")
        if not parent_url and video_id:
            parent_url = f"https://www.youtube.com/watch?v={video_id}"
        if _is_http_url(parent_url):
            return parent_url
    return ""


def _resolve_original_url(uap: UAPRecord) -> str:
    fallback_url = uap.content.url if uap.content else None
    if _is_http_url(fallback_url):
        return str(fallback_url)

    raw = uap.raw if isinstance(uap.raw, dict) else {}
    platform_meta = (
        raw.get("platform_meta") if isinstance(raw.get("platform_meta"), dict) else {}
    )
    hierarchy = raw.get("hierarchy") if isinstance(raw.get("hierarchy"), dict) else {}
    parent_url = _platform_parent_url(uap, platform_meta, hierarchy)

    doc_type = str(uap.content.doc_type if uap.content else "").strip().lower()
    source_id = ""
    if uap.ingest and uap.ingest.source:
        source_id = str(uap.ingest.source.source_id or "").strip()

    if _is_http_url(parent_url):
        if doc_type == "comment" and source_id:
            return _with_query_param(parent_url, "lc", source_id)
        return parent_url
    return ""


__all__ = ["build_batch_completed_payload"]
