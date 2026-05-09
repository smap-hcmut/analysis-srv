from __future__ import annotations

import asyncio
import copy
import json
import time
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import text

from internal.http.errors import APIError, BadRequestError
from internal.http.helpers import as_list, fmt_number, percent_change
from internal.http.project_client import ProjectServiceClient
from pkg.postgre.postgres import PostgresDatabase


PLATFORM_META: dict[str, dict[str, str]] = {
    "TIKTOK": {"name": "TikTok", "color": "var(--platform-tiktok)", "chartColor": "var(--chart-1)"},
    "FACEBOOK": {"name": "Facebook", "color": "#1877f2", "chartColor": "var(--chart-2)"},
    "YOUTUBE": {"name": "YouTube", "color": "#ff0000", "chartColor": "var(--chart-3)"},
}


def public_sentiment_label(raw_label: Any, score: float | None = None) -> str:
    """Map persisted sentiment to the public API label.

    The NLP pipeline stores scores on a signed scale (-0.5/0/0.5 today), so
    using 0..1 thresholds here hides every positive mention. Persisted labels
    are the source of truth; score fallback is only for older rows.
    """
    label = str(raw_label or "").strip().upper()
    if label == "POSITIVE":
        return "positive"
    if label == "NEGATIVE":
        return "negative"
    if label == "NEUTRAL":
        return "neutral"

    value = float(score or 0.0)
    if value > 0.25:
        return "positive"
    if value < -0.25:
        return "negative"
    return "neutral"


@dataclass
class AnalyticsContext:
    campaign_id: str
    campaign_name: str
    project_ids: list[str]
    project_names: dict[str, str]


@dataclass
class CachedResponse:
    value: dict[str, Any]
    expires_at: float


class AnalyticsService:
    def __init__(self, db: PostgresDatabase, project_client: ProjectServiceClient, query_timeout_ms: int = 25_000):
        self.db = db
        self.project_client = project_client
        self._response_cache: dict[tuple[Any, ...], CachedResponse] = {}
        self._query_timeout_ms = max(1, int(query_timeout_ms))
        # Keep analytics DB pressure bounded even when UI fires all dashboard
        # endpoints at once (kpis/platforms/sentiment/keywords/posts).
        self._db_concurrency_guard: asyncio.Semaphore = asyncio.Semaphore(8)
        # Negative cache for campaigns whose queries hit statement_timeout. Without
        # this, every UI refresh re-issues 7 expensive queries and burns 25s each
        # on the server, blocking the connection pool for the rest of the system.
        self._timeout_cache: dict[tuple[Any, ...], float] = {}
        self._timeout_cache_ttl: float = 60.0
        self._posts_window_size: int = 240
        self._posts_cache_ttl: float = 120.0

    def _resolve_query_timeout_ms(self, project_count: int, query_profile: str = "normal") -> int:
        # Avoid long-running fan-out queries from saturating the Postgres pool.
        # Bigger campaigns are more likely to hit expensive joins, so give them
        # more time rather than fail earlier with a hard 30s cap.
        timeout_ms = self._query_timeout_ms
        if project_count >= 200:
            timeout_ms = max(timeout_ms, 55_000)
        elif project_count >= 100:
            timeout_ms = max(timeout_ms, 45_000)
        elif project_count >= 50:
            timeout_ms = max(timeout_ms, 35_000)
        elif project_count >= 25:
            timeout_ms = max(timeout_ms, 30_000)
        # Heap endpoint aggregates nested structures and can be unexpectedly
        # expensive, allow a little extra time when explicitly called.
        if query_profile == "heavy":
            timeout_ms = int(timeout_ms * 1.15)

        timeout_ms = max(8_000, min(timeout_ms, 70_000))
        return timeout_ms

    def _timeout_key(self, campaign_id: str, scope: tuple[Any, ...] | None = None) -> tuple[Any, ...]:
        return (campaign_id, *(scope or ()))

    def _is_timed_out(self, campaign_id: str, scope: tuple[Any, ...] | None = None) -> bool:
        key = self._timeout_key(campaign_id, scope)
        until = self._timeout_cache.get(key)
        if not until:
            return False
        if until <= time.time():
            self._timeout_cache.pop(key, None)
            return False
        return True

    def _mark_timed_out(self, campaign_id: str, scope: tuple[Any, ...] | None = None) -> None:
        self._timeout_cache[self._timeout_key(campaign_id, scope)] = time.time() + self._timeout_cache_ttl

    def _cache_get(self, key: tuple[Any, ...]) -> dict[str, Any] | None:
        cached = self._response_cache.get(key)
        if not cached or cached.expires_at <= time.time():
            if cached:
                self._response_cache.pop(key, None)
            return None
        return copy.deepcopy(cached.value)

    def _cache_set(self, key: tuple[Any, ...], value: dict[str, Any], ttl_seconds: float = 30.0) -> dict[str, Any]:
        self._response_cache[key] = CachedResponse(
            value=copy.deepcopy(value),
            expires_at=time.time() + ttl_seconds,
        )
        return value

    async def build_context(self, campaign_id: str) -> AnalyticsContext:
        self._validate_uuid(campaign_id)
        campaign = await self.project_client.get_campaign_projects(campaign_id)
        return AnalyticsContext(
            campaign_id=campaign.id,
            campaign_name=campaign.name,
            project_ids=campaign.project_ids,
            project_names=self.project_client.project_name_map(campaign),
        )

    async def get_kpis(self, campaign_id: str, source_kind: str = "all") -> dict[str, Any]:
        source_kind = self._normalize_source_kind(source_kind)
        return await self._guarded(campaign_id, self._compute_kpis(campaign_id, source_kind), ("kpis", source_kind))

    async def _compute_kpis(self, campaign_id: str, source_kind: str = "all") -> dict[str, Any]:
        source_kind = self._normalize_source_kind(source_kind)
        cache_key = ("kpis", campaign_id, source_kind)
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        ctx = await self.build_context(campaign_id)
        if not ctx.project_ids:
            return self._cache_set(cache_key, {
                "metrics": [
                    {"label": "Total Mentions", "value": 0, "formatted": "0", "change": 0, "sparkline": [], "icon": "activity"},
                    {"label": "Sentiment Score", "value": 0, "formatted": "0%", "change": 0, "sparkline": [], "icon": "smile", "suffix": "%"},
                    {"label": "Engagement", "value": 0, "formatted": "0", "change": 0, "sparkline": [], "icon": "heart"},
                    {"label": "Audience Reach", "value": 0, "formatted": "0", "change": 0, "sparkline": [], "icon": "users"},
                ],
                "engagement": {"views": 0, "likes": 0, "comments": 0, "shares": 0},
            })

        query_timeout_ms = self._resolve_query_timeout_ms(len(ctx.project_ids), "heavy")
        source_filters = self._source_kind_pre_filters(source_kind)
        summary_rows, spark_rows = await self._fetch_many(
            (
                self._base_cte(ctx.project_ids, source_filters)
                + """
SELECT
  COUNT(*) AS total_mentions,
  COALESCE(AVG(overall_sentiment_score) * 100, 0) AS avg_sentiment,
  COALESCE(SUM(engagement_score), 0) AS sum_engagement,
  COALESCE(SUM(reach_estimate), 0) AS sum_reach,
  COALESCE(SUM((uap_metadata->'engagement'->>'views')::bigint), 0) AS sum_views,
  COALESCE(SUM((uap_metadata->'engagement'->>'likes')::bigint), 0) AS sum_likes,
  COALESCE(SUM((uap_metadata->'engagement'->>'comments')::bigint), 0) AS sum_comments,
  COALESCE(SUM((uap_metadata->'engagement'->>'shares')::bigint), 0) AS sum_shares,
  COUNT(*) FILTER (WHERE content_created_at >= NOW() - INTERVAL '30 days') AS current_mentions,
  COUNT(*) FILTER (WHERE content_created_at >= NOW() - INTERVAL '60 days' AND content_created_at < NOW() - INTERVAL '30 days') AS previous_mentions,
  COALESCE(AVG(overall_sentiment_score) FILTER (WHERE content_created_at >= NOW() - INTERVAL '30 days') * 100, 0) AS current_sentiment,
  COALESCE(AVG(overall_sentiment_score) FILTER (WHERE content_created_at >= NOW() - INTERVAL '60 days' AND content_created_at < NOW() - INTERVAL '30 days') * 100, 0) AS previous_sentiment,
  COALESCE(SUM(engagement_score) FILTER (WHERE content_created_at >= NOW() - INTERVAL '30 days'), 0) AS current_engagement,
  COALESCE(SUM(engagement_score) FILTER (WHERE content_created_at >= NOW() - INTERVAL '60 days' AND content_created_at < NOW() - INTERVAL '30 days'), 0) AS previous_engagement,
  COALESCE(SUM(reach_estimate) FILTER (WHERE content_created_at >= NOW() - INTERVAL '30 days'), 0) AS current_reach,
  COALESCE(SUM(reach_estimate) FILTER (WHERE content_created_at >= NOW() - INTERVAL '60 days' AND content_created_at < NOW() - INTERVAL '30 days'), 0) AS previous_reach
FROM deduped_post_insight
"""
            ),
            (
                self._base_cte(ctx.project_ids, source_filters)
                + """
SELECT
  TO_CHAR(date_trunc('month', content_created_at), 'YYYY-MM') AS month,
  COUNT(*) AS mentions,
  COALESCE(AVG(overall_sentiment_score) * 100, 0) AS sentiment,
  COALESCE(SUM(engagement_score), 0) AS engagement,
  COALESCE(SUM(reach_estimate), 0) AS reach
FROM deduped_post_insight
WHERE content_created_at >= NOW() - INTERVAL '12 months'
GROUP BY 1
ORDER BY 1
"""
            ),
            project_count=len(ctx.project_ids),
            query_timeout_ms=query_timeout_ms,
        )
        t = summary_rows[0] if summary_rows else {}
        return self._cache_set(cache_key, {
            "metrics": [
                {
                    "label": "Total Mentions",
                    "value": int(t.get("total_mentions", 0)),
                    "formatted": fmt_number(int(t.get("total_mentions", 0))),
                    "change": percent_change(t.get("current_mentions", 0), t.get("previous_mentions", 0)),
                    "sparkline": [int(row["mentions"]) for row in spark_rows],
                    "icon": "activity",
                },
                {
                    "label": "Sentiment Score",
                    "value": round(float(t.get("avg_sentiment", 0)), 1),
                    "formatted": f"{round(float(t.get('avg_sentiment', 0)), 1)}%",
                    "change": percent_change(t.get("current_sentiment", 0), t.get("previous_sentiment", 0)),
                    "sparkline": [float(row["sentiment"]) for row in spark_rows],
                    "icon": "smile",
                    "suffix": "%",
                },
                {
                    "label": "Engagement",
                    "value": int(t.get("sum_engagement", 0)),
                    "formatted": fmt_number(int(t.get("sum_engagement", 0))),
                    "change": percent_change(t.get("current_engagement", 0), t.get("previous_engagement", 0)),
                    "sparkline": [float(row["engagement"]) for row in spark_rows],
                    "icon": "heart",
                },
                {
                    "label": "Audience Reach",
                    "value": int(t.get("sum_reach", 0)),
                    "formatted": fmt_number(int(t.get("sum_reach", 0))),
                    "change": percent_change(t.get("current_reach", 0), t.get("previous_reach", 0)),
                    "sparkline": [int(row["reach"]) for row in spark_rows],
                    "icon": "users",
                },
            ],
            "engagement": {
                "views": int(t.get("sum_views", 0)),
                "likes": int(t.get("sum_likes", 0)),
                "comments": int(t.get("sum_comments", 0)),
                "shares": int(t.get("sum_shares", 0)),
            },
        })

    async def get_platforms(self, campaign_id: str, source_kind: str = "all") -> dict[str, Any]:
        source_kind = self._normalize_source_kind(source_kind)
        return await self._guarded(campaign_id, self._compute_platforms(campaign_id, source_kind), ("platforms", source_kind))

    async def _compute_platforms(self, campaign_id: str, source_kind: str = "all") -> dict[str, Any]:
        source_kind = self._normalize_source_kind(source_kind)
        cache_key = ("platforms", campaign_id, source_kind)
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        ctx = await self.build_context(campaign_id)
        if not ctx.project_ids:
            return self._cache_set(cache_key, {"stats": [], "timeSeries": [], "months": []})

        query_timeout_ms = self._resolve_query_timeout_ms(len(ctx.project_ids), "normal")
        source_filters = self._source_kind_pre_filters(source_kind)
        platform_rows, ts_rows = await self._fetch_many(
            (
                self._base_cte(ctx.project_ids, source_filters)
                + """
SELECT
  UPPER(platform) AS platform,
  COUNT(*) AS mentions,
  COALESCE(AVG(overall_sentiment_score) * 100, 0) AS avg_sentiment,
  COALESCE(SUM(engagement_score), 0) AS sum_engagement,
  COALESCE(SUM(reach_estimate), 0) AS sum_reach,
  COUNT(*) FILTER (WHERE content_created_at >= NOW() - INTERVAL '30 days') AS current_mentions,
  COUNT(*) FILTER (WHERE content_created_at >= NOW() - INTERVAL '60 days' AND content_created_at < NOW() - INTERVAL '30 days') AS previous_mentions
FROM deduped_post_insight
WHERE platform IS NOT NULL
GROUP BY UPPER(platform)
ORDER BY COUNT(*) DESC
"""
            ),
            (
                self._base_cte(ctx.project_ids, source_filters)
                + """
SELECT
  TO_CHAR(date_trunc('month', content_created_at), 'YYYY-MM') AS month,
  UPPER(platform) AS platform,
  COUNT(*) AS mentions
FROM deduped_post_insight
WHERE platform IS NOT NULL
  AND content_created_at >= NOW() - INTERVAL '12 months'
GROUP BY 1, 2
ORDER BY 1
"""
            ),
            project_count=len(ctx.project_ids),
            query_timeout_ms=query_timeout_ms,
        )

        stats = []
        for row in platform_rows:
            platform = row["platform"]
            meta = PLATFORM_META.get(platform, {"name": platform, "color": "#888", "chartColor": "#888"})
            current_mentions = int(row["current_mentions"])
            previous_mentions = int(row["previous_mentions"])
            stats.append({
                "platform": platform.lower(),
                "name": meta["name"],
                "mentions": int(row["mentions"]),
                "mentionsChange": percent_change(current_mentions, previous_mentions),
                "engagement": fmt_number(float(row["sum_engagement"])),
                "engagementRaw": int(float(row["sum_engagement"])),
                "sentiment": round(float(row["avg_sentiment"])),
                "reach": int(row["sum_reach"]),
                "status": "active",
                "color": meta["color"],
            })

        for key, meta in PLATFORM_META.items():
            if not any(item["platform"] == key.lower() for item in stats):
                stats.append({
                    "platform": key.lower(),
                    "name": meta["name"],
                    "mentions": 0,
                    "mentionsChange": 0,
                    "engagement": "0",
                    "engagementRaw": 0,
                    "sentiment": 0,
                    "reach": 0,
                    "status": "inactive",
                    "color": meta["color"],
                })

        months = sorted({str(row["month"]) for row in ts_rows})
        time_series = []
        for key, meta in PLATFORM_META.items():
            time_series.append({
                "label": meta["name"],
                "color": meta["chartColor"],
                "data": [
                    int(next((r["mentions"] for r in ts_rows if r["month"] == month and r["platform"] == key), 0))
                    for month in months
                ],
            })

        return self._cache_set(cache_key, {"stats": stats, "timeSeries": time_series, "months": months})

    async def get_sentiment(self, campaign_id: str, source_kind: str = "all") -> dict[str, Any]:
        source_kind = self._normalize_source_kind(source_kind)
        return await self._guarded(campaign_id, self._compute_sentiment(campaign_id, source_kind), ("sentiment", source_kind))

    async def _compute_sentiment(self, campaign_id: str, source_kind: str = "all") -> dict[str, Any]:
        source_kind = self._normalize_source_kind(source_kind)
        cache_key = ("sentiment", campaign_id, source_kind)
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        ctx = await self.build_context(campaign_id)
        if not ctx.project_ids:
            return self._cache_set(cache_key, {
                "donut": [
                    {"label": "Positive", "value": 0, "color": "var(--success)"},
                    {"label": "Neutral", "value": 0, "color": "var(--warning)"},
                    {"label": "Negative", "value": 0, "color": "var(--danger)"},
                ],
                "timeline": [],
                "months": [],
                "pulse": 0,
                "total": 0,
            })

        query_timeout_ms = self._resolve_query_timeout_ms(len(ctx.project_ids), "heavy")
        source_filters = self._source_kind_pre_filters(source_kind)
        summary_rows, timeline_rows = await self._fetch_many(
            (
                self._base_cte(ctx.project_ids, source_filters)
                + """
SELECT
  COUNT(*) FILTER (WHERE UPPER(COALESCE(overall_sentiment, '')) = 'POSITIVE') AS positive_count,
  COUNT(*) FILTER (WHERE UPPER(COALESCE(overall_sentiment, '')) = 'NEUTRAL') AS neutral_count,
  COUNT(*) FILTER (WHERE UPPER(COALESCE(overall_sentiment, '')) = 'NEGATIVE') AS negative_count,
  COALESCE(AVG(overall_sentiment_score) * 100, 0) AS avg_sentiment,
  COUNT(*) AS total
FROM deduped_post_insight
"""
            ),
            (
                self._base_cte(ctx.project_ids, source_filters)
                + """
SELECT
  TO_CHAR(date_trunc('month', content_created_at), 'YYYY-MM') AS month,
  UPPER(platform) AS platform,
  COALESCE(AVG(overall_sentiment_score) * 100, 0) AS avg_sentiment
FROM deduped_post_insight
WHERE platform IS NOT NULL
  AND content_created_at >= NOW() - INTERVAL '12 months'
GROUP BY 1, 2
ORDER BY 1
"""
            ),
            project_count=len(ctx.project_ids),
            query_timeout_ms=query_timeout_ms,
        )

        summary = summary_rows[0] if summary_rows else {}
        months = sorted({str(row["month"]) for row in timeline_rows})
        platforms = sorted({str(row["platform"]) for row in timeline_rows})
        timeline = []
        for platform in platforms:
            meta = PLATFORM_META.get(platform, {"name": platform, "chartColor": "#888"})
            timeline.append({
                "label": meta["name"],
                "color": meta["chartColor"],
                "data": [
                    round(float(next((r["avg_sentiment"] for r in timeline_rows if r["month"] == month and r["platform"] == platform), 0)))
                    for month in months
                ],
            })

        return self._cache_set(cache_key, {
            "donut": [
                {"label": "positive", "value": int(summary.get("positive_count", 0)), "color": "var(--success)"},
                {"label": "neutral", "value": int(summary.get("neutral_count", 0)), "color": "var(--warning)"},
                {"label": "negative", "value": int(summary.get("negative_count", 0)), "color": "var(--danger)"},
            ],
            "timeline": timeline,
            "months": months,
            "pulse": round(float(summary.get("avg_sentiment", 0)), 1),
            "total": int(summary.get("total", 0)),
        })

    async def get_keywords(self, campaign_id: str, limit: int = 50, source_kind: str = "all") -> dict[str, Any]:
        source_kind = self._normalize_source_kind(source_kind)
        return await self._guarded(campaign_id, self._compute_keywords(campaign_id, limit, source_kind), ("keywords", limit, source_kind))

    async def _compute_keywords(self, campaign_id: str, limit: int = 50, source_kind: str = "all") -> dict[str, Any]:
        source_kind = self._normalize_source_kind(source_kind)
        cache_key = ("keywords", campaign_id, limit, source_kind)
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        ctx = await self.build_context(campaign_id)
        if not ctx.project_ids:
            return self._cache_set(cache_key, {"keywords": [], "wordCloud": []})

        query_timeout_ms = self._resolve_query_timeout_ms(len(ctx.project_ids), "heavy")
        source_filters = self._source_kind_pre_filters(source_kind)
        sql = (
            self._base_cte(ctx.project_ids, source_filters)
            + """
SELECT
  kw AS keyword,
  COUNT(*) AS volume,
  COALESCE(AVG(overall_sentiment_score) * 100, 0) AS avg_sentiment,
  COUNT(*) FILTER (WHERE content_created_at >= NOW() - INTERVAL '30 days') AS current_volume,
  COUNT(*) FILTER (WHERE content_created_at >= NOW() - INTERVAL '60 days' AND content_created_at < NOW() - INTERVAL '30 days') AS previous_volume
FROM deduped_post_insight,
     LATERAL unnest(keywords) AS kw
WHERE keywords IS NOT NULL
  AND array_length(keywords, 1) > 0
GROUP BY kw
ORDER BY COUNT(*) DESC
LIMIT :limit
"""
        )
        rows = await self._fetch_all(
            sql,
            {"limit": limit},
            timeout_ms=query_timeout_ms,
        )
        keywords = []
        for row in rows:
            sentiment = round(float(row["avg_sentiment"]))
            keywords.append({
                "text": str(row["keyword"]),
                "volume": int(row["volume"]),
                "sentiment": sentiment,
                "change": percent_change(row["current_volume"], row["previous_volume"]),
            })
        word_cloud = [
            {
                "text": item["text"],
                "value": item["volume"],
                "color": "var(--accent)",
                "opacity": 0.4 if item["sentiment"] < 40 else 0.65 if item["sentiment"] < 70 else 1,
            }
            for item in keywords
        ]
        return self._cache_set(cache_key, {"keywords": keywords, "wordCloud": word_cloud})

    async def get_posts(
        self,
        campaign_id: str,
        platform: str = "all",
        sentiment: str = "all",
        sort: str = "engagement",
        limit: int = 30,
        offset: int = 0,
        source_kind: str = "all",
    ) -> dict[str, Any]:
        source_kind = self._normalize_source_kind(source_kind)
        timeout_scope = (
            "posts",
            str(platform or "all").strip().lower(),
            str(sentiment or "all").strip().lower(),
            "time" if str(sort or "").strip().lower() == "time" else "engagement",
            source_kind,
        )
        return await self._guarded(
            campaign_id,
            self._compute_posts(campaign_id, platform, sentiment, sort, limit, offset, source_kind),
            timeout_scope,
        )

    async def _compute_posts(
        self,
        campaign_id: str,
        platform: str = "all",
        sentiment: str = "all",
        sort: str = "engagement",
        limit: int = 30,
        offset: int = 0,
        source_kind: str = "all",
    ) -> dict[str, Any]:
        source_kind = self._normalize_source_kind(source_kind)
        limit = max(1, min(int(limit), 100))
        offset = max(0, int(offset))
        platform_key = str(platform or "all").strip().lower()
        sentiment_key = str(sentiment or "all").strip().lower()
        sort_key = "time" if str(sort or "").strip().lower() == "time" else "engagement"
        platform_filter = platform_key.upper() if platform_key.upper() in PLATFORM_META else "all"
        sentiment_filter = sentiment_key if sentiment_key in {"positive", "negative", "neutral"} else "all"
        cache_key = ("posts", campaign_id, platform_filter.lower(), sentiment_filter, sort_key, limit, offset, source_kind)
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        ctx = await self.build_context(campaign_id)
        if not ctx.project_ids:
            return self._cache_set(cache_key, {"posts": [], "total": 0}, ttl_seconds=10.0)

        requested_end = offset + limit
        use_window_cache = requested_end <= self._posts_window_size
        window_key = (
            "posts-window",
            campaign_id,
            platform_filter.lower(),
            sentiment_filter,
            sort_key,
            source_kind,
            self._posts_window_size,
        )
        if use_window_cache:
            cached_window = self._cache_get(window_key)
            if cached_window is not None:
                window_posts = list(cached_window.get("posts") or [])
                total = int(cached_window.get("total") or 0)
                return self._cache_set(
                    cache_key,
                    {"posts": window_posts[offset:requested_end], "total": total},
                    ttl_seconds=self._posts_cache_ttl,
                )

        conditions = []
        query_limit = self._posts_window_size if use_window_cache else limit
        query_offset = 0 if use_window_cache else offset
        params: dict[str, Any] = {"limit": query_limit, "offset": query_offset}
        pre_filters: list[str] = self._source_kind_pre_filters(source_kind)
        if platform_filter != "all":
            platform_expr = "COALESCE(NULLIF(UPPER(pi.platform), ''), 'UNKNOWN')"
            pre_filters.append(f"{platform_expr} = '{self._escape(platform_filter)}'")
            conditions.append("COALESCE(NULLIF(UPPER(platform), ''), 'UNKNOWN') = :platform")
            params["platform"] = platform_filter
        if sentiment_filter == "positive":
            pre_filters.append("UPPER(COALESCE(pi.overall_sentiment, '')) = 'POSITIVE'")
            conditions.append("UPPER(COALESCE(overall_sentiment, '')) = 'POSITIVE'")
        elif sentiment_filter == "negative":
            pre_filters.append("UPPER(COALESCE(pi.overall_sentiment, '')) = 'NEGATIVE'")
            conditions.append("UPPER(COALESCE(overall_sentiment, '')) = 'NEGATIVE'")
        elif sentiment_filter == "neutral":
            pre_filters.append("UPPER(COALESCE(pi.overall_sentiment, '')) = 'NEUTRAL'")
            conditions.append("UPPER(COALESCE(overall_sentiment, '')) = 'NEUTRAL'")
        where = " AND ".join(conditions) if conditions else "1 = 1"
        order_by = "content_created_at DESC NULLS LAST" if sort_key == "time" else "engagement_score DESC NULLS LAST"
        final_order_by = "p.content_created_at DESC NULLS LAST" if sort_key == "time" else "p.engagement_score DESC NULLS LAST"

        sql = (
            self._posts_base_cte(ctx.project_ids, pre_filters)
            + f"""
filtered_post_insight AS (
  SELECT *
  FROM latest_post_insight
  WHERE {where}
),
total_post_insight AS (
  SELECT COUNT(*) AS total_count
  FROM filtered_post_insight
),
page_post_insight AS (
  SELECT *
  FROM filtered_post_insight
  ORDER BY {order_by}
  LIMIT :limit OFFSET :offset
)
SELECT
  p.id::text,
  LOWER(p.platform) AS platform,
  COALESCE(pi.content, '') AS content,
  COALESCE(TO_CHAR(p.content_created_at, 'YYYY-MM-DD"T"HH24:MI:SS"Z"'), '') AS content_created_at,
  COALESCE(p.overall_sentiment, 'NEUTRAL') AS overall_sentiment,
  COALESCE(p.overall_sentiment_score, 0) AS overall_sentiment_score,
  COALESCE(p.engagement_score, 0) AS engagement_score,
  COALESCE(p.reach_estimate, 0) AS reach_estimate,
  COALESCE(p.risk_level, 'LOW') AS risk_level,
  COALESCE(p.keywords, '{{}}') AS keywords,
  COALESCE(pi.uap_metadata::text, '{{}}') AS uap_metadata,
  COALESCE(pi.uap_metadata #>> '{{platform_meta,smap,source_kind}}', '') AS source_kind,
  COALESCE(pi.uap_metadata #>> '{{platform_meta,smap,data_source_id}}', '') AS data_source_id,
  COALESCE(pi.uap_metadata #>> '{{platform_meta,smap,target_id}}', '') AS target_id,
  t.total_count
FROM page_post_insight p
JOIN analysis.post_insight pi ON pi.id = p.id
CROSS JOIN total_post_insight t
ORDER BY {final_order_by}
"""
        )
        query_timeout_ms = self._resolve_query_timeout_ms(len(ctx.project_ids), "normal")
        rows = await self._fetch_all(sql, params, timeout_ms=query_timeout_ms)
        total = int(rows[0]["total_count"]) if rows else 0
        posts = []
        for row in rows:
            try:
                uap = json.loads(row["uap_metadata"]) if isinstance(row["uap_metadata"], str) else (row["uap_metadata"] or {})
            except json.JSONDecodeError:
                uap = {}
            engagement = uap.get("engagement") or {}
            score = float(row["overall_sentiment_score"])
            label = public_sentiment_label(row["overall_sentiment"], score)
            posts.append({
                "id": str(row["id"]),
                "platform": str(row["platform"] or "unknown"),
                "author": str(uap.get("author_display_name") or uap.get("author_username") or "Unknown"),
                "authorUsername": str(uap.get("author_username") or ""),
                "authorFollowers": int(uap.get("author_followers") or 0),
                "authorVerified": bool(uap.get("author_is_verified") or False),
                "content": str(row["content"] or ""),
                "time": str(row["content_created_at"] or ""),
                "url": str(uap.get("url") or ""),
                "sentiment": label,
                "sentimentScore": score,
                "engagement": int(float(row["engagement_score"])),
                "views": int(engagement.get("views") or 0),
                "likes": int(engagement.get("likes") or 0),
                "comments": int(engagement.get("comments") or 0),
                "shares": int(engagement.get("shares") or 0),
                "keywords": as_list(row["keywords"]),
                "riskLevel": str(row["risk_level"]),
                "hashtags": [str(item) for item in (uap.get("hashtags") or [])],
                "sourceKind": str(row["source_kind"] or "legacy"),
                "dataSourceId": str(row["data_source_id"] or ""),
                "targetId": str(row["target_id"] or ""),
            })
        if use_window_cache:
            self._cache_set(
                window_key,
                {"posts": posts, "total": total},
                ttl_seconds=self._posts_cache_ttl,
            )
            return self._cache_set(
                cache_key,
                {"posts": posts[offset:requested_end], "total": total},
                ttl_seconds=self._posts_cache_ttl,
            )
        return self._cache_set(cache_key, {"posts": posts, "total": total}, ttl_seconds=self._posts_cache_ttl)

    async def get_project_stats(self, campaign_id: str, source_kind: str = "all") -> dict[str, Any]:
        source_kind = self._normalize_source_kind(source_kind)
        return await self._guarded(campaign_id, self._compute_project_stats(campaign_id, source_kind), ("project-stats", source_kind))

    async def _compute_project_stats(self, campaign_id: str, source_kind: str = "all") -> dict[str, Any]:
        source_kind = self._normalize_source_kind(source_kind)
        cache_key = ("project-stats", campaign_id, source_kind)
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        ctx = await self.build_context(campaign_id)
        if not ctx.project_ids:
            return self._cache_set(cache_key, {"stats": []})

        sql = (
            self._base_cte(ctx.project_ids, self._source_kind_pre_filters(source_kind))
            + """
SELECT
  project_id::text AS project_id,
  COUNT(*) AS mentions,
  COALESCE(AVG(overall_sentiment_score) * 100, 0) AS avg_sentiment,
  STRING_AGG(DISTINCT UPPER(platform), ',' ORDER BY UPPER(platform)) AS platforms
FROM deduped_post_insight
WHERE platform IS NOT NULL
GROUP BY project_id
"""
        )
        query_timeout_ms = self._resolve_query_timeout_ms(len(ctx.project_ids), "normal")
        rows = await self._fetch_all(sql, timeout_ms=query_timeout_ms)
        return self._cache_set(cache_key, {
            "stats": [
                {
                    "project_id": str(row["project_id"]),
                    "mentions": int(row["mentions"]),
                    "avg_sentiment": round(float(row["avg_sentiment"]), 1),
                    "platforms": [item for item in str(row["platforms"] or "").split(",") if item],
                }
                for row in rows
            ]
        })

    async def get_heap(self, campaign_id: str, source_kind: str = "all") -> dict[str, Any]:
        source_kind = self._normalize_source_kind(source_kind)
        return await self._guarded(campaign_id, self._compute_heap(campaign_id, source_kind), ("heap", source_kind))

    async def _compute_heap(self, campaign_id: str, source_kind: str = "all") -> dict[str, Any]:
        source_kind = self._normalize_source_kind(source_kind)
        cache_key = ("heap", campaign_id, source_kind)
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        ctx = await self.build_context(campaign_id)
        if not ctx.project_ids:
            return self._cache_set(cache_key, {"tree": None})

        query_timeout_ms = self._resolve_query_timeout_ms(len(ctx.project_ids), "heavy")
        project_names, project_stats_rows, keyword_rows = await self._fetch_heap_parts(
            ctx,
            query_timeout_ms=query_timeout_ms,
            source_kind=source_kind,
        )

        project_stats = {str(row["project_id"]): row for row in project_stats_rows}
        keywords_by_project: dict[str, list[dict[str, Any]]] = {}
        for row in keyword_rows:
            pid = str(row["project_id"])
            keywords_by_project.setdefault(pid, []).append({
                "id": f"kw-{pid}-{row['keyword']}",
                "type": "keyword",
                "name": str(row["keyword"]),
                "metrics": {
                    "mentions": int(row["volume"]),
                    "engagement": int(float(row["sum_engagement"])),
                    "sentiment": round(float(row["avg_sentiment"])),
                    "childCount": 0,
                },
            })

        project_children = []
        for project_id in ctx.project_ids:
            stats = project_stats.get(project_id)
            children = keywords_by_project.get(project_id, [])
            project_children.append({
                "id": f"proj-{project_id}",
                "type": "project",
                "name": project_names.get(project_id, project_id),
                "metrics": {
                    "mentions": int(stats["mentions"]) if stats else 0,
                    "engagement": int(float(stats["sum_engagement"])) if stats else 0,
                    "sentiment": round(float(stats["avg_sentiment"])) if stats else 0,
                    "childCount": len(children),
                },
                "children": children,
            })

        total_mentions = sum(item["metrics"]["mentions"] for item in project_children)
        total_engagement = sum(item["metrics"]["engagement"] for item in project_children)
        avg_sentiment = round(sum(item["metrics"]["sentiment"] for item in project_children) / len(project_children)) if project_children else 0
        return self._cache_set(cache_key, {
            "tree": {
                "id": f"camp-{ctx.campaign_id}",
                "type": "campaign",
                "name": ctx.campaign_name,
                "metrics": {
                    "mentions": total_mentions,
                    "engagement": total_engagement,
                    "sentiment": avg_sentiment,
                    "childCount": len(project_children),
                },
                "children": project_children,
            }
        })

    async def _fetch_heap_parts(self, ctx: AnalyticsContext, query_timeout_ms: int, source_kind: str = "all"):
        source_filters = self._source_kind_pre_filters(source_kind)
        project_stats_rows, keyword_rows = await self._fetch_many(
            (
                self._base_cte(ctx.project_ids, source_filters)
                + """
SELECT
  project_id::text AS project_id,
  COUNT(*) AS mentions,
  COALESCE(AVG(overall_sentiment_score) * 100, 0) AS avg_sentiment,
  COALESCE(SUM(engagement_score), 0) AS sum_engagement
FROM deduped_post_insight
GROUP BY project_id
"""
            ),
            (
                self._base_cte(ctx.project_ids, source_filters)
                + """
, ranked AS (
  SELECT
    project_id::text AS project_id,
    kw AS keyword,
    COUNT(*) AS volume,
    AVG(overall_sentiment_score) * 100 AS avg_sentiment,
    SUM(engagement_score) AS sum_engagement,
    ROW_NUMBER() OVER (PARTITION BY project_id ORDER BY COUNT(*) DESC) AS rn
  FROM deduped_post_insight,
       LATERAL unnest(keywords) AS kw
  WHERE keywords IS NOT NULL
    AND array_length(keywords, 1) > 0
  GROUP BY project_id, kw
)
SELECT project_id, keyword, volume, COALESCE(avg_sentiment, 0) AS avg_sentiment, COALESCE(sum_engagement, 0) AS sum_engagement
FROM ranked
WHERE rn <= 10
ORDER BY project_id, volume DESC
"""
            ),
            project_count=len(ctx.project_ids),
            query_timeout_ms=query_timeout_ms,
        )
        return ctx.project_names, project_stats_rows, keyword_rows

    async def _fetch_many(self, *queries: str, project_count: int, query_timeout_ms: int):
        # Keep query fan-out serialized per endpoint and bounded by an explicit
        # semaphore. Concurrent fan-out can create DB pool storms during
        # dashboard refresh bursts.
        rows: list[list[dict[str, Any]]] = []
        for query in queries:
            rows.append(
                await self._fetch_all(
                    query,
                    timeout_ms=query_timeout_ms or self._resolve_query_timeout_ms(project_count),
                )
            )
        return rows

    def _is_statement_timeout(self, exc: BaseException) -> bool:
        # SQLAlchemy wraps the asyncpg error; sqlstate 57014 == query_canceled.
        orig = getattr(exc, "orig", None)
        sqlstate = getattr(orig, "sqlstate", None) or getattr(exc, "pgcode", None)
        if sqlstate == "57014":
            return True
        msg = str(exc).lower()
        return "statement timeout" in msg or "querycancelederror" in type(exc).__name__.lower()

    async def _guarded(self, campaign_id: str, coro, timeout_scope: tuple[Any, ...] | None = None):
        """Run an analytics coroutine, mark the campaign as 'too heavy' on
        statement_timeout so later requests fail fast instead of spending
        another timeout window holding pool slots."""
        if self._is_timed_out(campaign_id, timeout_scope):
            coro.close()
            raise APIError(504, "analytics query exceeded server time limit")
        try:
            return await coro
        except Exception as exc:
            if self._is_statement_timeout(exc):
                self._mark_timed_out(campaign_id, timeout_scope)
                raise APIError(504, "analytics query exceeded server time limit") from exc
            raise

    async def _fetch_all(
        self,
        query: str,
        params: dict[str, Any] | None = None,
        timeout_ms: int | None = None,
    ) -> list[dict[str, Any]]:
        if timeout_ms is None:
            timeout_ms = self._query_timeout_ms
        timeout_ms = max(1, int(timeout_ms))
        async with self._db_concurrency_guard:
            async with self.db.get_session() as session:
                await session.execute(text(f"SET LOCAL statement_timeout = {timeout_ms}"))
                await session.execute(text("SET LOCAL work_mem = '64MB'"))
                result = await session.execute(text(query), params or {})
                return [dict(row._mapping) for row in result.fetchall()]

    def _source_identity_expr(self, alias: str) -> str:
        """Canonical source identity expression used for dedup and grouping.

        Order matters: prefer explicit source identifiers, then stable UAP IDs,
        then URL, finally row UUID as last-resort fallback.
        """
        return (
            "COALESCE("
            f"NULLIF({alias}.source_id, ''), "
            f"NULLIF({alias}.uap_metadata->>'post_id', ''), "
            f"NULLIF({alias}.uap_metadata->>'comment_id', ''), "
            f"NULLIF({alias}.uap_metadata->>'video_id', ''), "
            f"NULLIF({alias}.uap_metadata->>'url', ''), "
            f"{alias}.id::text"
            ")"
        )

    def _normalize_source_kind(self, value: str | None) -> str:
        raw = str(value or "all").strip().lower()
        aliases = {
            "focused": "stalker",
            "focused_page": "stalker",
            "focused_profile": "stalker",
            "stalkers": "stalker",
            "profile": "stalker",
            "profiles": "stalker",
            "crawler": "keyword",
            "crawling": "keyword",
            "keyword_search": "keyword",
            "search": "keyword",
            "general": "keyword",
            "legacy": "keyword",
        }
        raw = aliases.get(raw, raw)
        return raw if raw in {"all", "stalker", "keyword"} else "all"

    def _source_kind_pre_filters(self, source_kind: str) -> list[str]:
        kind = self._normalize_source_kind(source_kind)
        source_expr = "COALESCE(pi.uap_metadata #>> '{platform_meta,smap,source_kind}', '')"
        if kind == "stalker":
            return [f"{source_expr} IN ('focused_page', 'focused_profile')"]
        if kind == "keyword":
            return [f"({source_expr} = '' OR {source_expr} = 'keyword_search')"]
        return []

    def _apply_relevance_filter(self, pre_filters: list[str] | None = None) -> bool:
        joined_filters = " ".join(pre_filters or [])
        return "focused_page" not in joined_filters and "focused_profile" not in joined_filters

    def _base_cte(self, project_ids: list[str], pre_filters: list[str] | None = None) -> str:
        quoted_ids = ", ".join(f"'{self._escape(project_id)}'" for project_id in project_ids)
        identity_expr = self._source_identity_expr("pi")
        extra_where = "\n".join(f"    AND {condition}" for condition in (pre_filters or []))
        relevance_where = "    AND pi.business_relevance_score >= 0.45" if self._apply_relevance_filter(pre_filters) else ""
        return f"""
WITH latest_post_insight AS (
  SELECT DISTINCT ON (
    COALESCE(NULLIF(UPPER(pi.platform), ''), 'UNKNOWN'),
    {identity_expr}
  )
    pi.*
  FROM analysis.post_insight pi
  WHERE project_id IN ({quoted_ids})
{relevance_where}
{extra_where}
  ORDER BY
    COALESCE(NULLIF(UPPER(pi.platform), ''), 'UNKNOWN'),
    {identity_expr},
    COALESCE(pi.updated_at, pi.analyzed_at, pi.ingested_at, pi.created_at) DESC NULLS LAST,
    pi.created_at DESC NULLS LAST,
    pi.id DESC
), deduped_post_insight AS (
  SELECT *
  FROM latest_post_insight
)
"""

    def _posts_base_cte(self, project_ids: list[str], pre_filters: list[str] | None = None) -> str:
        quoted_ids = ", ".join(f"'{self._escape(project_id)}'" for project_id in project_ids)
        identity_expr = self._source_identity_expr("pi")
        extra_where = "\n".join(f"    AND {condition}" for condition in (pre_filters or []))
        return f"""
WITH latest_post_insight AS (
  SELECT DISTINCT ON (
    COALESCE(NULLIF(UPPER(pi.platform), ''), 'UNKNOWN'),
    {identity_expr}
  )
    pi.id,
    pi.platform,
    pi.content_created_at,
    pi.overall_sentiment,
    pi.overall_sentiment_score,
    pi.engagement_score,
    pi.reach_estimate,
    pi.risk_level,
    pi.keywords
  FROM analysis.post_insight pi
  WHERE project_id IN ({quoted_ids})
{"    AND pi.business_relevance_score >= 0.45" if self._apply_relevance_filter(pre_filters) else ""}
{extra_where}
  ORDER BY
    COALESCE(NULLIF(UPPER(pi.platform), ''), 'UNKNOWN'),
    {identity_expr},
    COALESCE(pi.updated_at, pi.analyzed_at, pi.ingested_at, pi.created_at) DESC NULLS LAST,
    pi.created_at DESC NULLS LAST,
    pi.id DESC
),
"""

    def _escape(self, value: str) -> str:
        return value.replace("'", "''")

    def _validate_uuid(self, value: str) -> None:
        try:
            UUID(value)
        except ValueError as exc:
            raise BadRequestError("campaignId must be a valid UUID") from exc
