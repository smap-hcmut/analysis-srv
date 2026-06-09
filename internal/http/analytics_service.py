from __future__ import annotations

import asyncio
import copy
import csv
import html
import io
import json
import os
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
    "TIKTOK": {
        "name": "TikTok",
        "color": "var(--platform-tiktok)",
        "chartColor": "var(--chart-1)",
    },
    "FACEBOOK": {
        "name": "Facebook",
        "color": "#1877f2",
        "chartColor": "var(--chart-2)",
    },
    "YOUTUBE": {"name": "YouTube", "color": "#ff0000", "chartColor": "var(--chart-3)"},
}
PLATFORM_CHANGE_MIN_PREVIOUS_MENTIONS = 30
POST_EXPORT_COLUMNS = [
    "id",
    "platform",
    "contentType",
    "author",
    "authorUsername",
    "time",
    "sentiment",
    "sentimentScore",
    "engagement",
    "views",
    "likes",
    "comments",
    "shares",
    "sourceKind",
    "dataSourceId",
    "targetId",
    "rootId",
    "parentId",
    "url",
    "keywords",
    "content",
]


def is_reliable_platform_mentions_change(
    current: int | float, previous: int | float
) -> bool:
    current_n = float(current)
    previous_n = float(previous)
    return not (
        current_n > previous_n and previous_n < PLATFORM_CHANGE_MIN_PREVIOUS_MENTIONS
    )


def _csv_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return "; ".join(str(item) for item in value)
    return str(value)


def posts_to_csv(posts: list[dict[str, Any]]) -> str:
    buffer = io.StringIO()
    writer = csv.DictWriter(
        buffer, fieldnames=POST_EXPORT_COLUMNS, extrasaction="ignore"
    )
    writer.writeheader()
    for post in posts:
        writer.writerow(
            {column: _csv_value(post.get(column)) for column in POST_EXPORT_COLUMNS}
        )
    return buffer.getvalue()


def _svg_text(value: Any, limit: int | None = None) -> str:
    text_value = _csv_value(value).replace("\n", " ").replace("\r", " ").strip()
    if limit is not None and len(text_value) > limit:
        text_value = f"{text_value[: max(0, limit - 1)]}…"
    return html.escape(text_value, quote=False)


def posts_to_svg(
    posts: list[dict[str, Any]], filters: dict[str, Any], total: int
) -> str:
    width = 1600
    row_height = 34
    top_offset = 118
    height = max(260, top_offset + (len(posts) + 1) * row_height + 32)
    generated_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    metadata = json.dumps(
        {
            "title": "Top Mentions by Platform",
            "generatedAt": generated_at,
            "filters": filters,
            "returnedRows": len(posts),
            "totalRows": total,
        },
        ensure_ascii=False,
    ).replace("]]>", "]]]]><![CDATA[>")

    header = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
<metadata><![CDATA[{metadata}]]></metadata>
<style>
  .bg {{ fill: #fbf8f2; }}
  .panel {{ fill: #fffdf8; stroke: #e7dfd2; stroke-width: 1.2; }}
  .title {{ font: 700 26px Inter, Arial, sans-serif; fill: #1d1a16; }}
  .meta {{ font: 500 13px Inter, Arial, sans-serif; fill: #817363; }}
  .th {{ font: 700 12px Inter, Arial, sans-serif; fill: #817363; text-transform: uppercase; }}
  .td {{ font: 500 13px Inter, Arial, sans-serif; fill: #3d352b; }}
  .muted {{ fill: #8f806e; }}
  .positive {{ fill: #2f9d68; }}
  .negative {{ fill: #d83a34; }}
  .neutral {{ fill: #c47a22; }}
  .line {{ stroke: #eee6da; stroke-width: 1; }}
</style>
<rect class="bg" width="{width}" height="{height}"/>
<rect class="panel" x="24" y="24" width="{width - 48}" height="{height - 48}" rx="22"/>
<text class="title" x="52" y="68">Top Mentions by Platform</text>
<text class="meta" x="52" y="94">Rows: {len(posts)} of {total} · Generated: {_svg_text(generated_at)} · Filters: {_svg_text(filters)}</text>
"""
    columns = [
        (52, "Platform"),
        (150, "Type"),
        (240, "Author"),
        (420, "Time"),
        (610, "Sentiment"),
        (720, "Eng."),
        (805, "Content"),
    ]
    rows = [
        header,
        f'<line class="line" x1="52" y1="{top_offset - 18}" x2="{width - 52}" y2="{top_offset - 18}"/>',
    ]
    for x, label in columns:
        rows.append(f'<text class="th" x="{x}" y="{top_offset}">{label}</text>')
    rows.append(
        f'<line class="line" x1="52" y1="{top_offset + 12}" x2="{width - 52}" y2="{top_offset + 12}"/>'
    )

    for index, post in enumerate(posts):
        y = top_offset + 38 + index * row_height
        sentiment = str(post.get("sentiment") or "neutral").lower()
        sentiment_class = (
            sentiment if sentiment in {"positive", "negative", "neutral"} else "neutral"
        )
        rows.extend(
            [
                f'<text class="td muted" x="52" y="{y}">{_svg_text(post.get("platform"), 18)}</text>',
                f'<text class="td muted" x="150" y="{y}">{_svg_text(post.get("contentType"), 18)}</text>',
                f'<text class="td" x="240" y="{y}">{_svg_text(post.get("author"), 28)}</text>',
                f'<text class="td muted" x="420" y="{y}">{_svg_text(post.get("time"), 28)}</text>',
                f'<text class="td {sentiment_class}" x="610" y="{y}">{_svg_text(sentiment, 16)}</text>',
                f'<text class="td" x="720" y="{y}">{_svg_text(post.get("engagement"), 10)}</text>',
                f'<text class="td" x="805" y="{y}">{_svg_text(post.get("content"), 128)}</text>',
            ]
        )
        rows.append(
            f'<line class="line" x1="52" y1="{y + 11}" x2="{width - 52}" y2="{y + 11}"/>'
        )

    rows.append("</svg>")
    return "\n".join(rows)


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


def extract_source_url(metadata: dict[str, Any]) -> str:
    """Return the best available platform permalink from crawler metadata."""
    direct_keys = (
        "url",
        "post_url",
        "original_url",
        "source_url",
        "web_url",
        "parent_post_url",
        "comment_url",
        "share_url",
        "permalink_url",
    )
    for key in direct_keys:
        value = str(metadata.get(key) or "").strip()
        if value:
            return value

    platform_meta = (
        metadata.get("platform_meta")
        if isinstance(metadata.get("platform_meta"), dict)
        else {}
    )
    for platform_key in ("youtube", "tiktok", "facebook"):
        platform_data = (
            platform_meta.get(platform_key)
            if isinstance(platform_meta.get(platform_key), dict)
            else {}
        )
        for key in (
            "comment_url",
            "parent_url",
            "video_url",
            "post_url",
            "permalink_url",
            "url",
        ):
            value = str(platform_data.get(key) or "").strip()
            if value:
                return value

    youtube = (
        platform_meta.get("youtube")
        if isinstance(platform_meta.get("youtube"), dict)
        else {}
    )
    video_id = str(youtube.get("video_id") or metadata.get("video_id") or "").strip()
    if video_id:
        comment_id = str(
            metadata.get("comment_id") or metadata.get("source_id") or ""
        ).strip()
        suffix = f"&lc={comment_id}" if comment_id.startswith("Ug") else ""
        return f"https://www.youtube.com/watch?v={video_id}{suffix}"

    tiktok = (
        platform_meta.get("tiktok")
        if isinstance(platform_meta.get("tiktok"), dict)
        else {}
    )
    tiktok_video_id = str(
        tiktok.get("video_id") or metadata.get("video_id") or ""
    ).strip()
    author = (
        str(metadata.get("author_username") or tiktok.get("author_username") or "")
        .strip()
        .lstrip("@")
    )
    if tiktok_video_id and author:
        return f"https://www.tiktok.com/@{author}/video/{tiktok_video_id}"

    return ""


@dataclass
class AnalyticsContext:
    campaign_id: str
    campaign_name: str
    project_ids: list[str]
    project_names: dict[str, str]


@dataclass(frozen=True)
class AnalyticsScope:
    source_kind: str = "all"
    project_ids: tuple[str, ...] = ()
    keywords: tuple[str, ...] = ()
    content_type: str = "all"

    def cache_key(self, include_content_type: bool = False) -> tuple[Any, ...]:
        base: tuple[Any, ...] = (self.source_kind, self.project_ids, self.keywords)
        if include_content_type:
            return (*base, self.content_type)
        return base

    def is_unfiltered(self) -> bool:
        """True when no scope-level filter would narrow the per-day rollup.

        The kpi_daily rollup pre-aggregates the relevance-filtered slice; it
        is correct only when the request does not further filter by
        source_kind / content_type / keywords.
        """
        return (
            self.source_kind in ("", "all")
            and self.content_type in ("", "all")
            and not self.keywords
        )


@dataclass
class CachedResponse:
    value: dict[str, Any]
    expires_at: float


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except (TypeError, ValueError):
        return default


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except (TypeError, ValueError):
        return default


class AnalyticsService:
    def __init__(
        self,
        db: PostgresDatabase,
        project_client: ProjectServiceClient,
        query_timeout_ms: int = 25_000,
    ):
        self.db = db
        self.project_client = project_client
        self._response_cache: dict[tuple[Any, ...], CachedResponse] = {}
        self._response_cache_ttl: float = max(
            5.0, _env_float("ANALYTICS_RESPONSE_CACHE_TTL_SECONDS", 180.0)
        )
        self._context_cache_ttl: float = max(
            30.0, _env_float("ANALYTICS_CONTEXT_CACHE_TTL_SECONDS", 300.0)
        )
        self._response_cache_max_entries: int = max(
            64, _env_int("ANALYTICS_RESPONSE_CACHE_MAX_ENTRIES", 512)
        )
        self._query_timeout_ms = max(1, int(query_timeout_ms))
        # Keep analytics DB pressure bounded even when UI fires all dashboard
        # endpoints at once (kpis/platforms/sentiment/keywords/posts). The
        # default was 8, but the Insight page alone issues 5 endpoints x 2
        # queries = 10 concurrent ops per render — half of them queued behind
        # the semaphore before the SQLAlchemy pool (20 + 10 overflow) was even
        # touched. Bumped to 16 so the bottleneck moves to Postgres itself,
        # which is where the timeout/negative-cache guard already lives.
        self._db_concurrency_guard: asyncio.Semaphore = asyncio.Semaphore(
            max(1, _env_int("ANALYTICS_DB_CONCURRENCY", 16))
        )
        # Negative cache for campaigns whose queries hit statement_timeout. Without
        # this, every UI refresh re-issues 7 expensive queries and burns 25s each
        # on the server, blocking the connection pool for the rest of the system.
        self._timeout_cache: dict[tuple[Any, ...], float] = {}
        self._timeout_cache_ttl: float = 60.0
        self._posts_window_size: int = 240
        self._posts_cache_ttl: float = 120.0
        self._posts_export_max_rows: int = max(
            100, _env_int("ANALYTICS_POSTS_EXPORT_MAX_ROWS", 20_000)
        )
        self._use_latest_mart = str(
            os.getenv("ANALYTICS_USE_LATEST_MART", "true")
        ).strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        self._source_quality_gate = str(
            os.getenv("ANALYTICS_SOURCE_QUALITY_GATE", "true")
        ).strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }

    def _resolve_query_timeout_ms(
        self, project_count: int, query_profile: str = "normal"
    ) -> int:
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

    def _timeout_key(
        self, campaign_id: str, scope: tuple[Any, ...] | None = None
    ) -> tuple[Any, ...]:
        return (campaign_id, *(scope or ()))

    def _is_timed_out(
        self, campaign_id: str, scope: tuple[Any, ...] | None = None
    ) -> bool:
        key = self._timeout_key(campaign_id, scope)
        until = self._timeout_cache.get(key)
        if not until:
            return False
        if until <= time.time():
            self._timeout_cache.pop(key, None)
            return False
        return True

    def _mark_timed_out(
        self, campaign_id: str, scope: tuple[Any, ...] | None = None
    ) -> None:
        self._timeout_cache[self._timeout_key(campaign_id, scope)] = (
            time.time() + self._timeout_cache_ttl
        )

    def _cache_get(self, key: tuple[Any, ...]) -> dict[str, Any] | None:
        cached = self._response_cache.get(key)
        if not cached or cached.expires_at <= time.time():
            if cached:
                self._response_cache.pop(key, None)
            return None
        return copy.deepcopy(cached.value)

    def _cache_set(
        self,
        key: tuple[Any, ...],
        value: dict[str, Any],
        ttl_seconds: float | None = None,
    ) -> dict[str, Any]:
        ttl = self._response_cache_ttl if ttl_seconds is None else ttl_seconds
        self._response_cache[key] = CachedResponse(
            value=copy.deepcopy(value),
            expires_at=time.time() + ttl,
        )
        self._prune_response_cache()
        return value

    def _prune_response_cache(self) -> None:
        if len(self._response_cache) <= self._response_cache_max_entries:
            return
        now = time.time()
        for key, cached in list(self._response_cache.items()):
            if cached.expires_at <= now:
                self._response_cache.pop(key, None)
        while len(self._response_cache) > self._response_cache_max_entries:
            oldest_key = min(
                self._response_cache,
                key=lambda key: self._response_cache[key].expires_at,
            )
            self._response_cache.pop(oldest_key, None)

    async def build_context(
        self, campaign_id: str, requested_project_ids: tuple[str, ...] = ()
    ) -> AnalyticsContext:
        self._validate_uuid(campaign_id)
        for project_id in requested_project_ids:
            self._validate_uuid(project_id)
        cache_key = ("context", campaign_id, requested_project_ids)
        cached = self._cache_get(cache_key)
        if cached is not None:
            return AnalyticsContext(
                campaign_id=str(cached.get("campaign_id") or campaign_id),
                campaign_name=str(cached.get("campaign_name") or ""),
                project_ids=[
                    str(project_id) for project_id in cached.get("project_ids") or []
                ],
                project_names={
                    str(key): str(value)
                    for key, value in dict(cached.get("project_names") or {}).items()
                },
            )

        campaign = await self.project_client.get_campaign_projects(campaign_id)
        if requested_project_ids:
            requested = set(requested_project_ids)
            project_ids = [
                project_id
                for project_id in campaign.project_ids
                if project_id in requested
            ]
        else:
            project_ids = campaign.project_ids
        context = AnalyticsContext(
            campaign_id=campaign.id,
            campaign_name=campaign.name,
            project_ids=project_ids,
            project_names=self.project_client.project_name_map(campaign),
        )
        self._cache_set(
            cache_key,
            {
                "campaign_id": context.campaign_id,
                "campaign_name": context.campaign_name,
                "project_ids": context.project_ids,
                "project_names": context.project_names,
            },
            ttl_seconds=self._context_cache_ttl,
        )
        return context

    def build_scope(
        self,
        source_kind: str = "all",
        project_ids: str | None = None,
        keywords: str | None = None,
        content_type: str = "all",
    ) -> AnalyticsScope:
        return AnalyticsScope(
            source_kind=self._normalize_source_kind(source_kind),
            project_ids=self._normalize_uuid_csv(project_ids),
            keywords=self._normalize_keyword_csv(keywords),
            content_type=self._normalize_content_type(content_type),
        )

    async def get_kpis(
        self,
        campaign_id: str,
        source_kind: str = "all",
        project_ids: str | None = None,
        keywords: str | None = None,
    ) -> dict[str, Any]:
        scope = self.build_scope(source_kind, project_ids, keywords)
        return await self._guarded(
            campaign_id,
            self._compute_kpis(campaign_id, scope),
            ("kpis", *scope.cache_key()),
        )

    async def _compute_kpis(
        self, campaign_id: str, scope: AnalyticsScope
    ) -> dict[str, Any]:
        cache_key = ("kpis", campaign_id, *scope.cache_key())
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        ctx = await self.build_context(campaign_id, scope.project_ids)
        # Fast path: when no scope filters narrow the query, the kpi_daily
        # rollup already holds the answer. Falls back to the on-demand
        # aggregate below if the rollup is empty (first deploy, refresh lag)
        # or returns no rows.
        if ctx.project_ids and scope.is_unfiltered():
            rollup = await self._compute_kpis_from_rollup(ctx.project_ids)
            if rollup is not None:
                return self._cache_set(cache_key, rollup)

        if not ctx.project_ids:
            return self._cache_set(
                cache_key,
                {
                    "metrics": [
                        {
                            "label": "Total Mentions",
                            "value": 0,
                            "formatted": "0",
                            "change": 0,
                            "sparkline": [],
                            "icon": "activity",
                        },
                        {
                            "label": "Sentiment Score",
                            "value": 0,
                            "formatted": "0%",
                            "change": 0,
                            "sparkline": [],
                            "icon": "smile",
                            "suffix": "%",
                        },
                        {
                            "label": "Engagement",
                            "value": 0,
                            "formatted": "0",
                            "change": 0,
                            "sparkline": [],
                            "icon": "heart",
                        },
                        {
                            "label": "Audience Reach",
                            "value": 0,
                            "formatted": "0",
                            "change": 0,
                            "sparkline": [],
                            "icon": "users",
                        },
                    ],
                    "engagement": {"views": 0, "likes": 0, "comments": 0, "shares": 0},
                },
            )

        query_timeout_ms = self._resolve_query_timeout_ms(len(ctx.project_ids), "heavy")
        source_filters = self._scope_pre_filters(scope)
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
        return self._cache_set(
            cache_key,
            {
                "metrics": [
                    {
                        "label": "Total Mentions",
                        "value": int(t.get("total_mentions", 0)),
                        "formatted": fmt_number(int(t.get("total_mentions", 0))),
                        "change": percent_change(
                            t.get("current_mentions", 0), t.get("previous_mentions", 0)
                        ),
                        "sparkline": [int(row["mentions"]) for row in spark_rows],
                        "icon": "activity",
                    },
                    {
                        "label": "Sentiment Score",
                        "value": round(float(t.get("avg_sentiment", 0)), 1),
                        "formatted": f"{round(float(t.get('avg_sentiment', 0)), 1)}%",
                        "change": percent_change(
                            t.get("current_sentiment", 0),
                            t.get("previous_sentiment", 0),
                        ),
                        "sparkline": [float(row["sentiment"]) for row in spark_rows],
                        "icon": "smile",
                        "suffix": "%",
                    },
                    {
                        "label": "Engagement",
                        "value": int(t.get("sum_engagement", 0)),
                        "formatted": fmt_number(int(t.get("sum_engagement", 0))),
                        "change": percent_change(
                            t.get("current_engagement", 0),
                            t.get("previous_engagement", 0),
                        ),
                        "sparkline": [float(row["engagement"]) for row in spark_rows],
                        "icon": "heart",
                    },
                    {
                        "label": "Audience Reach",
                        "value": int(t.get("sum_reach", 0)),
                        "formatted": fmt_number(int(t.get("sum_reach", 0))),
                        "change": percent_change(
                            t.get("current_reach", 0), t.get("previous_reach", 0)
                        ),
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
            },
        )

    async def _compute_kpis_from_rollup(
        self, project_ids: tuple[str, ...]
    ) -> dict[str, Any] | None:
        """Read the KPI dashboard payload from kpi_daily.

        Returns ``None`` if the rollup is empty for the requested projects so
        the caller can fall back to the on-demand aggregate. Hot path for the
        Insight tab: pulls O(rows-per-day) instead of O(rows-per-mention).
        """
        if not project_ids:
            return None

        rows = await self._fetch_all(
            """
WITH base AS (
  SELECT * FROM analysis.kpi_daily WHERE project_id = ANY(CAST(:project_ids AS text[]))
), summary AS (
  SELECT
    SUM(mentions)                                                           AS total_mentions,
    CASE WHEN SUM(mentions) > 0 THEN SUM(sentiment_sum) / SUM(mentions) * 100 ELSE 0 END AS avg_sentiment,
    SUM(engagement_sum)                                                     AS sum_engagement,
    SUM(reach_sum)                                                          AS sum_reach,
    SUM(views_sum)                                                          AS sum_views,
    SUM(likes_sum)                                                          AS sum_likes,
    SUM(comments_sum)                                                       AS sum_comments,
    SUM(shares_sum)                                                         AS sum_shares,
    SUM(mentions)        FILTER (WHERE bucket_date >= (CURRENT_DATE - 29))  AS current_mentions,
    SUM(mentions)        FILTER (WHERE bucket_date BETWEEN (CURRENT_DATE - 59) AND (CURRENT_DATE - 30)) AS previous_mentions,
    CASE WHEN SUM(mentions) FILTER (WHERE bucket_date >= (CURRENT_DATE - 29)) > 0
         THEN SUM(sentiment_sum) FILTER (WHERE bucket_date >= (CURRENT_DATE - 29)) / SUM(mentions) FILTER (WHERE bucket_date >= (CURRENT_DATE - 29)) * 100
         ELSE 0 END                                                          AS current_sentiment,
    CASE WHEN SUM(mentions) FILTER (WHERE bucket_date BETWEEN (CURRENT_DATE - 59) AND (CURRENT_DATE - 30)) > 0
         THEN SUM(sentiment_sum) FILTER (WHERE bucket_date BETWEEN (CURRENT_DATE - 59) AND (CURRENT_DATE - 30)) / SUM(mentions) FILTER (WHERE bucket_date BETWEEN (CURRENT_DATE - 59) AND (CURRENT_DATE - 30)) * 100
         ELSE 0 END                                                          AS previous_sentiment,
    SUM(engagement_sum)  FILTER (WHERE bucket_date >= (CURRENT_DATE - 29))  AS current_engagement,
    SUM(engagement_sum)  FILTER (WHERE bucket_date BETWEEN (CURRENT_DATE - 59) AND (CURRENT_DATE - 30)) AS previous_engagement,
    SUM(reach_sum)       FILTER (WHERE bucket_date >= (CURRENT_DATE - 29))  AS current_reach,
    SUM(reach_sum)       FILTER (WHERE bucket_date BETWEEN (CURRENT_DATE - 59) AND (CURRENT_DATE - 30)) AS previous_reach
  FROM base
), sparkline AS (
  SELECT
    TO_CHAR(date_trunc('month', bucket_date), 'YYYY-MM') AS month,
    SUM(mentions)                                          AS mentions,
    CASE WHEN SUM(mentions) > 0 THEN SUM(sentiment_sum) / SUM(mentions) * 100 ELSE 0 END AS sentiment,
    SUM(engagement_sum)                                    AS engagement,
    SUM(reach_sum)                                         AS reach
  FROM base
  WHERE bucket_date >= (CURRENT_DATE - INTERVAL '12 months')
  GROUP BY 1
  ORDER BY 1
)
SELECT
  (SELECT row_to_json(summary) FROM summary)                         AS summary,
  COALESCE((SELECT json_agg(sparkline ORDER BY month) FROM sparkline), '[]'::json) AS sparkline
""",
            params={"project_ids": list(project_ids)},
        )
        if not rows or not rows[0].get("summary"):
            return None
        summary = rows[0]["summary"] or {}
        if int(summary.get("total_mentions", 0) or 0) == 0:
            return None
        spark_rows = rows[0]["sparkline"] or []
        return {
            "metrics": [
                {
                    "label": "Total Mentions",
                    "value": int(summary.get("total_mentions", 0) or 0),
                    "formatted": fmt_number(int(summary.get("total_mentions", 0) or 0)),
                    "change": percent_change(
                        summary.get("current_mentions", 0) or 0,
                        summary.get("previous_mentions", 0) or 0,
                    ),
                    "sparkline": [int(row.get("mentions", 0) or 0) for row in spark_rows],
                    "icon": "activity",
                },
                {
                    "label": "Sentiment Score",
                    "value": round(float(summary.get("avg_sentiment", 0) or 0), 1),
                    "formatted": f"{round(float(summary.get('avg_sentiment', 0) or 0), 1)}%",
                    "change": percent_change(
                        summary.get("current_sentiment", 0) or 0,
                        summary.get("previous_sentiment", 0) or 0,
                    ),
                    "sparkline": [float(row.get("sentiment", 0) or 0) for row in spark_rows],
                    "icon": "smile",
                    "suffix": "%",
                },
                {
                    "label": "Engagement",
                    "value": int(summary.get("sum_engagement", 0) or 0),
                    "formatted": fmt_number(int(summary.get("sum_engagement", 0) or 0)),
                    "change": percent_change(
                        summary.get("current_engagement", 0) or 0,
                        summary.get("previous_engagement", 0) or 0,
                    ),
                    "sparkline": [float(row.get("engagement", 0) or 0) for row in spark_rows],
                    "icon": "heart",
                },
                {
                    "label": "Audience Reach",
                    "value": int(summary.get("sum_reach", 0) or 0),
                    "formatted": fmt_number(int(summary.get("sum_reach", 0) or 0)),
                    "change": percent_change(
                        summary.get("current_reach", 0) or 0,
                        summary.get("previous_reach", 0) or 0,
                    ),
                    "sparkline": [int(row.get("reach", 0) or 0) for row in spark_rows],
                    "icon": "users",
                },
            ],
            "engagement": {
                "views": int(summary.get("sum_views", 0) or 0),
                "likes": int(summary.get("sum_likes", 0) or 0),
                "comments": int(summary.get("sum_comments", 0) or 0),
                "shares": int(summary.get("sum_shares", 0) or 0),
            },
        }

    async def _compute_platforms_from_rollup(
        self, project_ids: tuple[str, ...]
    ) -> dict[str, Any] | None:
        """Fast path for /api/analytics/platforms backed by metrics_daily.

        Returns the same shape as ``_compute_platforms`` so the Insight tab
        renders without breaking: keys ``stats[*].mentions/mentionsChange/
        mentionsChangeReliable/mentionsCurrentPeriod/mentionsPreviousPeriod/
        engagement/engagementRaw/sentiment/reach/status/color/name`` plus a
        per-platform ``timeSeries`` aligned to ``months``.
        """
        if not project_ids:
            return None
        rows = await self._fetch_all(
            """
WITH base AS (
  SELECT * FROM analysis.metrics_daily
  WHERE project_id = ANY(CAST(:project_ids AS text[]))
), totals AS (
  SELECT UPPER(platform) AS platform,
         SUM(mentions)                                                                       AS mentions,
         SUM(mentions * sentiment_score)                                                     AS weighted_sentiment,
         SUM(engagement_sum)                                                                 AS engagement_sum,
         SUM(reach_sum)                                                                      AS reach_sum,
         SUM(mentions) FILTER (WHERE bucket_date >= (CURRENT_DATE - INTERVAL '30 days'))     AS current_mentions,
         SUM(mentions) FILTER (
           WHERE bucket_date >= (CURRENT_DATE - INTERVAL '60 days')
             AND bucket_date <  (CURRENT_DATE - INTERVAL '30 days')
         )                                                                                   AS previous_mentions
  FROM base
  GROUP BY UPPER(platform)
), ts AS (
  SELECT TO_CHAR(date_trunc('month', bucket_date), 'YYYY-MM') AS month,
         UPPER(platform) AS platform,
         SUM(mentions) AS mentions
  FROM base
  WHERE bucket_date >= (CURRENT_DATE - INTERVAL '12 months')
  GROUP BY 1, 2
  ORDER BY 1
)
SELECT
  (SELECT COALESCE(json_agg(row_to_json(totals)), '[]'::json) FROM totals) AS stats,
  (SELECT COALESCE(json_agg(row_to_json(ts) ORDER BY ts.month), '[]'::json) FROM ts) AS time_series
""",
            params={"project_ids": list(project_ids)},
        )
        if not rows:
            return None
        stats_raw = rows[0].get("stats") or []
        ts_raw = rows[0].get("time_series") or []
        total_mentions = sum(int(r.get("mentions", 0) or 0) for r in stats_raw)
        if total_mentions == 0:
            return None

        stats: list[dict[str, Any]] = []
        seen_platforms: set[str] = set()
        for r in stats_raw:
            platform = str(r.get("platform") or "UNKNOWN").upper()
            mentions = int(r.get("mentions", 0) or 0)
            weighted = float(r.get("weighted_sentiment", 0) or 0)
            current_mentions = int(r.get("current_mentions") or 0)
            previous_mentions = int(r.get("previous_mentions") or 0)
            engagement_sum = float(r.get("engagement_sum", 0) or 0)
            reach_sum = float(r.get("reach_sum", 0) or 0)
            meta = PLATFORM_META.get(
                platform, {"name": platform, "color": "#888", "chartColor": "#888"}
            )
            stats.append(
                {
                    "platform": platform.lower(),
                    "name": meta["name"],
                    "mentions": mentions,
                    "mentionsChange": percent_change(current_mentions, previous_mentions),
                    "mentionsChangeReliable": is_reliable_platform_mentions_change(
                        current_mentions, previous_mentions
                    ),
                    "mentionsCurrentPeriod": current_mentions,
                    "mentionsPreviousPeriod": previous_mentions,
                    "engagement": fmt_number(engagement_sum),
                    "engagementRaw": int(engagement_sum),
                    "sentiment": round(weighted / mentions * 100) if mentions else 0,
                    "reach": int(reach_sum),
                    "status": "active",
                    "color": meta["color"],
                }
            )
            seen_platforms.add(platform)

        for key, meta in PLATFORM_META.items():
            if key.upper() in seen_platforms:
                continue
            stats.append(
                {
                    "platform": key.lower(),
                    "name": meta["name"],
                    "mentions": 0,
                    "mentionsChange": 0,
                    "mentionsChangeReliable": True,
                    "mentionsCurrentPeriod": 0,
                    "mentionsPreviousPeriod": 0,
                    "engagement": "0",
                    "engagementRaw": 0,
                    "sentiment": 0,
                    "reach": 0,
                    "status": "inactive",
                    "color": meta["color"],
                }
            )

        months = sorted({str(r.get("month", "")) for r in ts_raw if r.get("month")})
        time_series = []
        for key, meta in PLATFORM_META.items():
            time_series.append(
                {
                    "label": meta["name"],
                    "color": meta["chartColor"],
                    "data": [
                        int(
                            next(
                                (
                                    int(r.get("mentions", 0) or 0)
                                    for r in ts_raw
                                    if str(r.get("month", "")) == m
                                    and str(r.get("platform", "")).upper() == key.upper()
                                ),
                                0,
                            )
                        )
                        for m in months
                    ],
                }
            )
        return {"stats": stats, "timeSeries": time_series, "months": months}

    async def _compute_sentiment_from_rollup(
        self, project_ids: tuple[str, ...]
    ) -> dict[str, Any] | None:
        """Fast path for /api/analytics/sentiment backed by metrics_daily.

        Mirrors ``_compute_sentiment``'s response: ``donut`` (raw counts so
        the UI can build percentages itself), ``timeline`` (per-platform
        avg sentiment series), ``months``, ``pulse``, ``total``.
        """
        if not project_ids:
            return None
        rows = await self._fetch_all(
            """
WITH base AS (
  SELECT * FROM analysis.metrics_daily
  WHERE project_id = ANY(CAST(:project_ids AS text[]))
), totals AS (
  SELECT UPPER(sentiment) AS sentiment, SUM(mentions) AS mentions
  FROM base
  GROUP BY UPPER(sentiment)
), summary AS (
  SELECT SUM(mentions)                    AS total_mentions,
         SUM(mentions * sentiment_score)  AS weighted_sentiment
  FROM base
), timeline AS (
  SELECT TO_CHAR(date_trunc('month', bucket_date), 'YYYY-MM') AS month,
         UPPER(platform) AS platform,
         SUM(mentions * sentiment_score) / NULLIF(SUM(mentions), 0) * 100 AS avg_sentiment
  FROM base
  WHERE bucket_date >= (CURRENT_DATE - INTERVAL '12 months')
    AND platform IS NOT NULL
  GROUP BY 1, 2
  ORDER BY 1
)
SELECT
  (SELECT COALESCE(json_agg(row_to_json(totals)), '[]'::json) FROM totals) AS totals,
  (SELECT row_to_json(summary) FROM summary) AS summary,
  (SELECT COALESCE(json_agg(row_to_json(timeline) ORDER BY timeline.month), '[]'::json) FROM timeline) AS timeline
""",
            params={"project_ids": list(project_ids)},
        )
        if not rows:
            return None
        totals_raw = rows[0].get("totals") or []
        timeline_raw = rows[0].get("timeline") or []
        summary = rows[0].get("summary") or {}
        grand_total = int(summary.get("total_mentions") or 0)
        if grand_total == 0:
            return None

        def _count_for(label_key: str) -> int:
            return next(
                (
                    int(r.get("mentions", 0) or 0)
                    for r in totals_raw
                    if str(r.get("sentiment", "")).upper() == label_key
                ),
                0,
            )

        donut = [
            {"label": "positive", "value": _count_for("POSITIVE"), "color": "var(--success)"},
            {"label": "neutral", "value": _count_for("NEUTRAL"), "color": "var(--warning)"},
            {"label": "negative", "value": _count_for("NEGATIVE"), "color": "var(--danger)"},
        ]

        months = sorted({str(r.get("month", "")) for r in timeline_raw if r.get("month")})
        platforms_seen = sorted({str(r.get("platform", "")).upper() for r in timeline_raw if r.get("platform")})
        timeline: list[dict[str, Any]] = []
        for platform in platforms_seen:
            meta = PLATFORM_META.get(platform, {"name": platform, "chartColor": "#888"})
            timeline.append(
                {
                    "label": meta["name"],
                    "color": meta["chartColor"],
                    "data": [
                        round(
                            float(
                                next(
                                    (
                                        r.get("avg_sentiment") or 0
                                        for r in timeline_raw
                                        if str(r.get("month", "")) == m
                                        and str(r.get("platform", "")).upper() == platform
                                    ),
                                    0,
                                )
                            )
                        )
                        for m in months
                    ],
                }
            )

        weighted = float(summary.get("weighted_sentiment") or 0)
        pulse = round((weighted / grand_total) * 100, 1) if grand_total else 0
        return {
            "donut": donut,
            "timeline": timeline,
            "months": months,
            "pulse": pulse,
            "total": grand_total,
        }

    async def get_platforms(
        self,
        campaign_id: str,
        source_kind: str = "all",
        project_ids: str | None = None,
        keywords: str | None = None,
    ) -> dict[str, Any]:
        scope = self.build_scope(source_kind, project_ids, keywords)
        return await self._guarded(
            campaign_id,
            self._compute_platforms(campaign_id, scope),
            ("platforms", *scope.cache_key()),
        )

    async def _compute_platforms(
        self, campaign_id: str, scope: AnalyticsScope
    ) -> dict[str, Any]:
        cache_key = ("platforms", campaign_id, *scope.cache_key())
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        ctx = await self.build_context(campaign_id, scope.project_ids)
        if ctx.project_ids and scope.is_unfiltered():
            rollup = await self._compute_platforms_from_rollup(ctx.project_ids)
            if rollup is not None:
                return self._cache_set(cache_key, rollup)
        if not ctx.project_ids:
            return self._cache_set(
                cache_key, {"stats": [], "timeSeries": [], "months": []}
            )

        query_timeout_ms = self._resolve_query_timeout_ms(
            len(ctx.project_ids), "normal"
        )
        source_filters = self._scope_pre_filters(scope)
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
            meta = PLATFORM_META.get(
                platform, {"name": platform, "color": "#888", "chartColor": "#888"}
            )
            current_mentions = int(row["current_mentions"])
            previous_mentions = int(row["previous_mentions"])
            mentions_change = percent_change(current_mentions, previous_mentions)
            stats.append(
                {
                    "platform": platform.lower(),
                    "name": meta["name"],
                    "mentions": int(row["mentions"]),
                    "mentionsChange": mentions_change,
                    "mentionsChangeReliable": is_reliable_platform_mentions_change(
                        current_mentions, previous_mentions
                    ),
                    "mentionsCurrentPeriod": current_mentions,
                    "mentionsPreviousPeriod": previous_mentions,
                    "engagement": fmt_number(float(row["sum_engagement"])),
                    "engagementRaw": int(float(row["sum_engagement"])),
                    "sentiment": round(float(row["avg_sentiment"])),
                    "reach": int(row["sum_reach"]),
                    "status": "active",
                    "color": meta["color"],
                }
            )

        for key, meta in PLATFORM_META.items():
            if not any(item["platform"] == key.lower() for item in stats):
                stats.append(
                    {
                        "platform": key.lower(),
                        "name": meta["name"],
                        "mentions": 0,
                        "mentionsChange": 0,
                        "mentionsChangeReliable": True,
                        "mentionsCurrentPeriod": 0,
                        "mentionsPreviousPeriod": 0,
                        "engagement": "0",
                        "engagementRaw": 0,
                        "sentiment": 0,
                        "reach": 0,
                        "status": "inactive",
                        "color": meta["color"],
                    }
                )

        months = sorted({str(row["month"]) for row in ts_rows})
        time_series = []
        for key, meta in PLATFORM_META.items():
            time_series.append(
                {
                    "label": meta["name"],
                    "color": meta["chartColor"],
                    "data": [
                        int(
                            next(
                                (
                                    r["mentions"]
                                    for r in ts_rows
                                    if r["month"] == month and r["platform"] == key
                                ),
                                0,
                            )
                        )
                        for month in months
                    ],
                }
            )

        return self._cache_set(
            cache_key, {"stats": stats, "timeSeries": time_series, "months": months}
        )

    async def get_sentiment(
        self,
        campaign_id: str,
        source_kind: str = "all",
        project_ids: str | None = None,
        keywords: str | None = None,
    ) -> dict[str, Any]:
        scope = self.build_scope(source_kind, project_ids, keywords)
        return await self._guarded(
            campaign_id,
            self._compute_sentiment(campaign_id, scope),
            ("sentiment", *scope.cache_key()),
        )

    async def _compute_sentiment(
        self, campaign_id: str, scope: AnalyticsScope
    ) -> dict[str, Any]:
        cache_key = ("sentiment", campaign_id, *scope.cache_key())
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        ctx = await self.build_context(campaign_id, scope.project_ids)
        if ctx.project_ids and scope.is_unfiltered():
            rollup = await self._compute_sentiment_from_rollup(ctx.project_ids)
            if rollup is not None:
                return self._cache_set(cache_key, rollup)
        if not ctx.project_ids:
            return self._cache_set(
                cache_key,
                {
                    "donut": [
                        {"label": "Positive", "value": 0, "color": "var(--success)"},
                        {"label": "Neutral", "value": 0, "color": "var(--warning)"},
                        {"label": "Negative", "value": 0, "color": "var(--danger)"},
                    ],
                    "timeline": [],
                    "months": [],
                    "pulse": 0,
                    "total": 0,
                },
            )

        query_timeout_ms = self._resolve_query_timeout_ms(len(ctx.project_ids), "heavy")
        source_filters = self._scope_pre_filters(scope)
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
            timeline.append(
                {
                    "label": meta["name"],
                    "color": meta["chartColor"],
                    "data": [
                        round(
                            float(
                                next(
                                    (
                                        r["avg_sentiment"]
                                        for r in timeline_rows
                                        if r["month"] == month
                                        and r["platform"] == platform
                                    ),
                                    0,
                                )
                            )
                        )
                        for month in months
                    ],
                }
            )

        return self._cache_set(
            cache_key,
            {
                "donut": [
                    {
                        "label": "positive",
                        "value": int(summary.get("positive_count", 0)),
                        "color": "var(--success)",
                    },
                    {
                        "label": "neutral",
                        "value": int(summary.get("neutral_count", 0)),
                        "color": "var(--warning)",
                    },
                    {
                        "label": "negative",
                        "value": int(summary.get("negative_count", 0)),
                        "color": "var(--danger)",
                    },
                ],
                "timeline": timeline,
                "months": months,
                "pulse": round(float(summary.get("avg_sentiment", 0)), 1),
                "total": int(summary.get("total", 0)),
            },
        )

    async def get_keywords(
        self,
        campaign_id: str,
        limit: int = 50,
        source_kind: str = "all",
        project_ids: str | None = None,
        keywords: str | None = None,
    ) -> dict[str, Any]:
        scope = self.build_scope(source_kind, project_ids, keywords)
        return await self._guarded(
            campaign_id,
            self._compute_keywords(campaign_id, limit, scope),
            ("keywords", limit, *scope.cache_key()),
        )

    async def _compute_keywords(
        self,
        campaign_id: str,
        limit: int = 50,
        scope: AnalyticsScope = AnalyticsScope(),
    ) -> dict[str, Any]:
        cache_key = ("keywords", campaign_id, limit, *scope.cache_key())
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        ctx = await self.build_context(campaign_id, scope.project_ids)
        if not ctx.project_ids:
            return self._cache_set(cache_key, {"keywords": [], "wordCloud": []})

        query_timeout_ms = self._resolve_query_timeout_ms(len(ctx.project_ids), "heavy")
        source_filters = self._scope_pre_filters(scope)
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
            keywords.append(
                {
                    "text": str(row["keyword"]),
                    "volume": int(row["volume"]),
                    "sentiment": sentiment,
                    "change": percent_change(
                        row["current_volume"], row["previous_volume"]
                    ),
                }
            )
        word_cloud = [
            {
                "text": item["text"],
                "value": item["volume"],
                "color": "var(--accent)",
                "opacity": 0.4
                if item["sentiment"] < 40
                else 0.65
                if item["sentiment"] < 70
                else 1,
            }
            for item in keywords
        ]
        return self._cache_set(
            cache_key, {"keywords": keywords, "wordCloud": word_cloud}
        )

    async def get_posts(
        self,
        campaign_id: str,
        platform: str = "all",
        sentiment: str = "all",
        sort: str = "engagement",
        limit: int = 30,
        offset: int = 0,
        source_kind: str = "all",
        project_ids: str | None = None,
        keywords: str | None = None,
        content_type: str = "all",
    ) -> dict[str, Any]:
        scope = self.build_scope(source_kind, project_ids, keywords, content_type)
        timeout_scope = (
            "posts",
            str(platform or "all").strip().lower(),
            str(sentiment or "all").strip().lower(),
            "time" if str(sort or "").strip().lower() == "time" else "engagement",
            *scope.cache_key(include_content_type=True),
        )
        return await self._guarded(
            campaign_id,
            self._compute_posts(
                campaign_id, platform, sentiment, sort, limit, offset, scope
            ),
            timeout_scope,
        )

    async def export_posts(
        self,
        campaign_id: str,
        export_format: str = "csv",
        platform: str = "all",
        sentiment: str = "all",
        sort: str = "engagement",
        source_kind: str = "all",
        project_ids: str | None = None,
        keywords: str | None = None,
        content_type: str = "all",
    ) -> dict[str, Any]:
        normalized_format = str(export_format or "csv").strip().lower()
        if normalized_format not in {"csv", "svg"}:
            raise BadRequestError("format must be csv or svg")

        scope = self.build_scope(source_kind, project_ids, keywords, content_type)
        sort_key = "time" if str(sort or "").strip().lower() == "time" else "engagement"
        timeout_scope = (
            "posts-export",
            normalized_format,
            str(platform or "all").strip().lower(),
            str(sentiment or "all").strip().lower(),
            sort_key,
            *scope.cache_key(include_content_type=True),
        )
        return await self._guarded(
            campaign_id,
            self._compute_posts_export(
                campaign_id, normalized_format, platform, sentiment, sort_key, scope
            ),
            timeout_scope,
        )

    async def _compute_posts_export(
        self,
        campaign_id: str,
        export_format: str,
        platform: str,
        sentiment: str,
        sort: str,
        scope: AnalyticsScope,
    ) -> dict[str, Any]:
        payload = await self._compute_posts(
            campaign_id,
            platform,
            sentiment,
            sort,
            self._posts_export_max_rows,
            0,
            scope,
            max_limit=self._posts_export_max_rows,
            cache_ttl=30.0,
        )
        posts = list(payload.get("posts") or [])
        total = int(payload.get("total") or len(posts))
        filters = {
            "campaignId": campaign_id,
            "platform": str(platform or "all").strip().lower() or "all",
            "sentiment": str(sentiment or "all").strip().lower() or "all",
            "contentType": scope.content_type,
            "sourceKind": scope.source_kind,
            "projectIds": list(scope.project_ids),
            "keywords": list(scope.keywords),
            "sort": "time"
            if str(sort or "").strip().lower() == "time"
            else "engagement",
        }
        safe_campaign = campaign_id.replace("-", "")[:12] or "campaign"
        filename = f"top-mentions-{safe_campaign}.{export_format}"
        if export_format == "svg":
            body = posts_to_svg(posts, filters, total)
            media_type = "image/svg+xml; charset=utf-8"
        else:
            body = posts_to_csv(posts)
            media_type = "text/csv; charset=utf-8"
        return {
            "body": body,
            "filename": filename,
            "media_type": media_type,
            "returned": len(posts),
            "total": total,
        }

    async def _compute_posts_from_rollup(
        self,
        project_ids: tuple[str, ...],
        sort_key: str,
        limit: int,
        offset: int,
    ) -> dict[str, Any] | None:
        """Fast path for /api/analytics/posts backed by posts_recent_top.

        Covers the unfiltered query, which is what the dashboard hits on every
        Insight tab open. Filtered queries (platform / sentiment / scope) keep
        falling back to the original full-table query path.
        """
        if not project_ids:
            return None
        order_clause = (
            "ORDER BY content_created_at DESC NULLS LAST, engagement_score DESC NULLS LAST"
            if sort_key == "time"
            else "ORDER BY engagement_score DESC NULLS LAST, content_created_at DESC NULLS LAST"
        )
        # posts_recent_top is rebuilt per project_id, so a TikTok comment that
        # matches more than one project in the campaign appears once per
        # project. DISTINCT ON collapses those shadows to a single row.
        rows = await self._fetch_all(
            f"""
WITH base AS (
  SELECT DISTINCT ON (COALESCE(NULLIF(UPPER(platform), ''), 'UNKNOWN'), uap_id)
    *
  FROM analysis.posts_recent_top
  WHERE project_id = ANY(CAST(:project_ids AS text[]))
  ORDER BY
    COALESCE(NULLIF(UPPER(platform), ''), 'UNKNOWN'),
    uap_id,
    engagement_score DESC NULLS LAST,
    content_created_at DESC NULLS LAST
), counted AS (
  SELECT COUNT(*) AS total FROM base
)
SELECT
  (SELECT total FROM counted) AS total,
  uap_id AS id,
  COALESCE(NULLIF(UPPER(platform), ''), 'UNKNOWN') AS platform,
  author,
  content_excerpt AS content,
  content_created_at,
  overall_sentiment,
  COALESCE(sentiment_score, 0) AS overall_sentiment_score,
  COALESCE(engagement_score, 0) AS engagement_score,
  uap_metadata,
  url
FROM base
{order_clause}
LIMIT :limit OFFSET :offset
""",
            params={
                "project_ids": list(project_ids),
                "limit": int(limit),
                "offset": int(offset),
            },
        )
        if not rows:
            return None
        total = int(rows[0].get("total", 0) or 0)
        if total == 0:
            return None
        posts = []
        for row in rows:
            try:
                uap = (
                    json.loads(row["uap_metadata"])
                    if isinstance(row["uap_metadata"], str)
                    else (row["uap_metadata"] or {})
                )
            except json.JSONDecodeError:
                uap = {}
            engagement = uap.get("engagement") or {}
            score = float(row["overall_sentiment_score"])
            label = public_sentiment_label(row["overall_sentiment"], score)
            posts.append(
                {
                    "id": str(row["id"]),
                    "platform": str(row["platform"] or "unknown"),
                    "author": str(
                        uap.get("author_display_name")
                        or uap.get("author_username")
                        or "Unknown"
                    ),
                    "authorUsername": str(uap.get("author_username") or ""),
                    "authorFollowers": int(uap.get("author_followers") or 0),
                    "authorVerified": bool(uap.get("author_is_verified") or False),
                    "content": str(row["content"] or ""),
                    "time": str(row["content_created_at"] or ""),
                    "url": extract_source_url(uap),
                    "sentiment": label,
                    "sentimentScore": score,
                    "engagement": int(float(row["engagement_score"])),
                    "views": int(engagement.get("views") or 0),
                    "likes": int(engagement.get("likes") or 0),
                    "comments": int(engagement.get("comments") or 0),
                    "shares": int(engagement.get("shares") or 0),
                }
            )
        return {"posts": posts, "total": total}

    async def _compute_posts(
        self,
        campaign_id: str,
        platform: str = "all",
        sentiment: str = "all",
        sort: str = "engagement",
        limit: int = 30,
        offset: int = 0,
        scope: AnalyticsScope = AnalyticsScope(),
        max_limit: int = 100,
        cache_ttl: float | None = None,
    ) -> dict[str, Any]:
        limit = max(1, min(int(limit), max(1, int(max_limit))))
        offset = max(0, int(offset))
        platform_key = str(platform or "all").strip().lower()
        sentiment_key = str(sentiment or "all").strip().lower()
        sort_key = "time" if str(sort or "").strip().lower() == "time" else "engagement"
        platform_filter = (
            platform_key.upper() if platform_key.upper() in PLATFORM_META else "all"
        )
        sentiment_filter = (
            sentiment_key
            if sentiment_key in {"positive", "negative", "neutral"}
            else "all"
        )
        cache_key = (
            "posts",
            campaign_id,
            platform_filter.lower(),
            sentiment_filter,
            sort_key,
            limit,
            offset,
            *scope.cache_key(include_content_type=True),
        )
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        ctx = await self.build_context(campaign_id, scope.project_ids)
        if not ctx.project_ids:
            return self._cache_set(
                cache_key, {"posts": [], "total": 0}, ttl_seconds=10.0
            )

        if (
            scope.is_unfiltered()
            and platform_filter == "all"
            and sentiment_filter == "all"
        ):
            rollup = await self._compute_posts_from_rollup(
                ctx.project_ids, sort_key, limit, offset
            )
            if rollup is not None:
                return self._cache_set(
                    cache_key, rollup, ttl_seconds=cache_ttl or self._posts_cache_ttl
                )

        requested_end = offset + limit
        use_window_cache = requested_end <= self._posts_window_size
        window_key = (
            "posts-window",
            campaign_id,
            platform_filter.lower(),
            sentiment_filter,
            sort_key,
            *scope.cache_key(include_content_type=True),
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
                    ttl_seconds=cache_ttl or self._posts_cache_ttl,
                )

        conditions = []
        query_limit = self._posts_window_size if use_window_cache else limit
        query_offset = 0 if use_window_cache else offset
        params: dict[str, Any] = {"limit": query_limit, "offset": query_offset}
        pre_filters: list[str] = self._scope_pre_filters(
            scope, include_content_type=True
        )
        if platform_filter != "all":
            platform_expr = "COALESCE(NULLIF(UPPER(pi.platform), ''), 'UNKNOWN')"
            pre_filters.append(f"{platform_expr} = '{self._escape(platform_filter)}'")
            conditions.append(
                "COALESCE(NULLIF(UPPER(platform), ''), 'UNKNOWN') = :platform"
            )
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
        order_by = (
            "content_created_at DESC NULLS LAST"
            if sort_key == "time"
            else "engagement_score DESC NULLS LAST"
        )
        final_order_by = (
            "p.content_created_at DESC NULLS LAST"
            if sort_key == "time"
            else "p.engagement_score DESC NULLS LAST"
        )

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
  {self._content_type_expr("pi")} AS content_type,
  COALESCE(pi.uap_metadata #>> '{{hierarchy,root_id}}', '') AS root_id,
  COALESCE(pi.uap_metadata #>> '{{hierarchy,parent_id}}', '') AS parent_id,
  t.total_count
FROM page_post_insight p
JOIN analysis.post_insight pi ON pi.id = p.id
CROSS JOIN total_post_insight t
ORDER BY {final_order_by}
"""
        )
        query_timeout_ms = self._resolve_query_timeout_ms(
            len(ctx.project_ids), "normal"
        )
        rows = await self._fetch_all(sql, params, timeout_ms=query_timeout_ms)
        total = int(rows[0]["total_count"]) if rows else 0
        posts = []
        for row in rows:
            try:
                uap = (
                    json.loads(row["uap_metadata"])
                    if isinstance(row["uap_metadata"], str)
                    else (row["uap_metadata"] or {})
                )
            except json.JSONDecodeError:
                uap = {}
            engagement = uap.get("engagement") or {}
            score = float(row["overall_sentiment_score"])
            label = public_sentiment_label(row["overall_sentiment"], score)
            posts.append(
                {
                    "id": str(row["id"]),
                    "platform": str(row["platform"] or "unknown"),
                    "author": str(
                        uap.get("author_display_name")
                        or uap.get("author_username")
                        or "Unknown"
                    ),
                    "authorUsername": str(uap.get("author_username") or ""),
                    "authorFollowers": int(uap.get("author_followers") or 0),
                    "authorVerified": bool(uap.get("author_is_verified") or False),
                    "content": str(row["content"] or ""),
                    "time": str(row["content_created_at"] or ""),
                    "url": extract_source_url(uap),
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
                    "contentType": str(row["content_type"] or "mention"),
                    "rootId": str(row["root_id"] or ""),
                    "parentId": str(row["parent_id"] or ""),
                }
            )
        if use_window_cache:
            self._cache_set(
                window_key,
                {"posts": posts, "total": total},
                ttl_seconds=cache_ttl or self._posts_cache_ttl,
            )
            return self._cache_set(
                cache_key,
                {"posts": posts[offset:requested_end], "total": total},
                ttl_seconds=cache_ttl or self._posts_cache_ttl,
            )
        return self._cache_set(
            cache_key,
            {"posts": posts, "total": total},
            ttl_seconds=cache_ttl or self._posts_cache_ttl,
        )

    async def get_heap(
        self,
        campaign_id: str,
        source_kind: str = "all",
        project_ids: str | None = None,
        keywords: str | None = None,
    ) -> dict[str, Any]:
        scope = self.build_scope(source_kind, project_ids, keywords)
        return await self._guarded(
            campaign_id,
            self._compute_heap(campaign_id, scope),
            ("heap", *scope.cache_key()),
        )

    async def _compute_heap(
        self, campaign_id: str, scope: AnalyticsScope
    ) -> dict[str, Any]:
        cache_key = ("heap", campaign_id, *scope.cache_key())
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        ctx = await self.build_context(campaign_id, scope.project_ids)
        if not ctx.project_ids:
            return self._cache_set(cache_key, {"tree": None})

        pre_filters = self._scope_pre_filters(scope)
        query_timeout_ms = self._resolve_query_timeout_ms(
            len(ctx.project_ids), "heavy"
        )

        project_sql = (
            self._base_cte(ctx.project_ids, pre_filters)
            + """
SELECT
  project_id::text AS project_id,
  COUNT(*) AS mentions,
  COALESCE(SUM(engagement_score), 0) AS engagement,
  COALESCE(AVG(overall_sentiment_score) * 100, 0) AS sentiment
FROM deduped_post_insight
GROUP BY project_id
"""
        )
        keyword_sql = (
            self._base_cte(ctx.project_ids, pre_filters)
            + """
SELECT
  project_id::text AS project_id,
  kw AS keyword,
  COUNT(*) AS mentions,
  COALESCE(SUM(engagement_score), 0) AS engagement,
  COALESCE(AVG(overall_sentiment_score) * 100, 0) AS sentiment,
  MODE() WITHIN GROUP (ORDER BY COALESCE(NULLIF(UPPER(platform), ''), 'UNKNOWN')) AS platform
FROM deduped_post_insight,
     LATERAL unnest(keywords) AS kw
WHERE keywords IS NOT NULL
  AND array_length(keywords, 1) > 0
GROUP BY project_id, kw
"""
        )

        project_rows, keyword_rows = await self._fetch_many(
            project_sql,
            keyword_sql,
            project_count=len(ctx.project_ids),
            query_timeout_ms=query_timeout_ms,
        )

        per_project_keywords: dict[str, list[dict[str, Any]]] = {}
        for row in keyword_rows:
            pid = str(row["project_id"])
            per_project_keywords.setdefault(pid, []).append(
                {
                    "keyword": str(row["keyword"] or "").strip(),
                    "mentions": int(row["mentions"] or 0),
                    "engagement": int(row["engagement"] or 0),
                    "sentiment": int(round(float(row["sentiment"] or 0))),
                    "platform": str(row["platform"] or "UNKNOWN"),
                }
            )

        KEYWORDS_PER_PROJECT = 8
        project_nodes: list[dict[str, Any]] = []
        total_mentions = 0
        total_engagement = 0
        weighted_sentiment = 0.0
        for row in project_rows:
            pid = str(row["project_id"])
            mentions = int(row["mentions"] or 0)
            engagement = int(row["engagement"] or 0)
            sentiment = int(round(float(row["sentiment"] or 0)))

            kw_list = sorted(
                per_project_keywords.get(pid, []),
                key=lambda k: k["mentions"],
                reverse=True,
            )[:KEYWORDS_PER_PROJECT]
            keyword_children = [
                {
                    "id": f"{pid}-kw-{idx + 1}",
                    "type": "keyword",
                    "name": kw["keyword"] or "(empty)",
                    "platform": kw["platform"],
                    "metrics": {
                        "mentions": kw["mentions"],
                        "engagement": kw["engagement"],
                        "sentiment": kw["sentiment"],
                        "childCount": 0,
                    },
                }
                for idx, kw in enumerate(kw_list)
                if kw["keyword"]
            ]

            project_nodes.append(
                {
                    "id": pid,
                    "type": "project",
                    "name": ctx.project_names.get(pid) or pid,
                    "metrics": {
                        "mentions": mentions,
                        "engagement": engagement,
                        "sentiment": sentiment,
                        "childCount": len(keyword_children),
                    },
                    "children": keyword_children,
                }
            )
            total_mentions += mentions
            total_engagement += engagement
            weighted_sentiment += sentiment * max(mentions, 1)

        if not project_nodes:
            return self._cache_set(cache_key, {"tree": None})

        denom = sum(max(int(p["metrics"]["mentions"]), 1) for p in project_nodes)
        campaign_sentiment = (
            int(round(weighted_sentiment / denom)) if denom else 0
        )
        tree = {
            "id": ctx.campaign_id,
            "type": "campaign",
            "name": ctx.campaign_name or ctx.campaign_id,
            "metrics": {
                "mentions": total_mentions,
                "engagement": total_engagement,
                "sentiment": campaign_sentiment,
                "childCount": len(project_nodes),
            },
            "children": project_nodes,
        }
        return self._cache_set(cache_key, {"tree": tree})

    async def get_project_stats(
        self,
        campaign_id: str,
        source_kind: str = "all",
        project_ids: str | None = None,
        keywords: str | None = None,
    ) -> dict[str, Any]:
        scope = self.build_scope(source_kind, project_ids, keywords)
        return await self._guarded(
            campaign_id,
            self._compute_project_stats(campaign_id, scope),
            ("project-stats", *scope.cache_key()),
        )

    async def _compute_project_stats(
        self, campaign_id: str, scope: AnalyticsScope
    ) -> dict[str, Any]:
        cache_key = ("project-stats", campaign_id, *scope.cache_key())
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        ctx = await self.build_context(campaign_id, scope.project_ids)
        if not ctx.project_ids:
            return self._cache_set(cache_key, {"stats": []})

        sql = (
            self._base_cte(ctx.project_ids, self._scope_pre_filters(scope))
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
        query_timeout_ms = self._resolve_query_timeout_ms(
            len(ctx.project_ids), "normal"
        )
        rows = await self._fetch_all(sql, timeout_ms=query_timeout_ms)
        return self._cache_set(
            cache_key,
            {
                "stats": [
                    {
                        "project_id": str(row["project_id"]),
                        "mentions": int(row["mentions"]),
                        "avg_sentiment": round(float(row["avg_sentiment"]), 1),
                        "platforms": [
                            item
                            for item in str(row["platforms"] or "").split(",")
                            if item
                        ],
                    }
                    for row in rows
                ]
            },
        )

    async def _fetch_many(
        self, *queries: str, project_count: int, query_timeout_ms: int
    ):
        # Keep query fan-out serialized per endpoint and bounded by an explicit
        # semaphore. Concurrent fan-out can create DB pool storms during
        # dashboard refresh bursts.
        rows: list[list[dict[str, Any]]] = []
        for query in queries:
            rows.append(
                await self._fetch_all(
                    query,
                    timeout_ms=query_timeout_ms
                    or self._resolve_query_timeout_ms(project_count),
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
        return (
            "statement timeout" in msg
            or "querycancelederror" in type(exc).__name__.lower()
        )

    async def _guarded(
        self, campaign_id: str, coro, timeout_scope: tuple[Any, ...] | None = None
    ):
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
                raise APIError(
                    504, "analytics query exceeded server time limit"
                ) from exc
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
                await session.execute(
                    text(f"SET LOCAL statement_timeout = {timeout_ms}")
                )
                await session.execute(text("SET LOCAL work_mem = '64MB'"))
                result = await session.execute(text(query), params or {})
                return [dict(row._mapping) for row in result.fetchall()]

    async def hide_crawl_target(
        self,
        target_id: str,
        data_source_id: str = "",
        reason: str = "stalker_flush",
        hidden_by: str = "ingest-srv",
    ) -> dict[str, Any]:
        self._validate_uuid(target_id)
        if data_source_id:
            self._validate_uuid(data_source_id)
        async with self.db.get_session() as session:
            await session.execute(
                text(
                    """
INSERT INTO analysis.hidden_crawl_targets (target_id, data_source_id, reason, hidden_by)
VALUES (
  CAST(:target_id AS uuid),
  NULLIF(CAST(:data_source_id AS text), '')::uuid,
  CAST(:reason AS text),
  CAST(:hidden_by AS text)
)
ON CONFLICT (target_id) DO UPDATE
SET data_source_id = COALESCE(EXCLUDED.data_source_id, analysis.hidden_crawl_targets.data_source_id),
    reason = EXCLUDED.reason,
    hidden_by = EXCLUDED.hidden_by,
    hidden_at = NOW()
"""
                ),
                {
                    "target_id": target_id,
                    "data_source_id": data_source_id,
                    "reason": reason or "stalker_flush",
                    "hidden_by": hidden_by or "ingest-srv",
                },
            )
            result = await session.execute(
                text(
                    """
UPDATE analysis.post_insight
SET uap_metadata = jsonb_set(
      jsonb_set(
        jsonb_set(
          jsonb_set(
            COALESCE(uap_metadata, '{}'::jsonb),
            '{platform_meta,smap,visibility}',
            to_jsonb('flushed'::text),
            true
          ),
          '{platform_meta,smap,deleted_at}',
          to_jsonb(NOW()::text),
          true
        ),
        '{platform_meta,smap,deleted_reason}',
        to_jsonb(CAST(:reason AS text)),
        true
      ),
      '{platform_meta,smap,deleted_by}',
      to_jsonb(CAST(:hidden_by AS text)),
      true
    ),
    updated_at = NOW()
WHERE uap_metadata @> CAST(:target_filter AS jsonb)
  AND COALESCE(uap_metadata #>> '{platform_meta,smap,visibility}', '') <> 'flushed'
  AND COALESCE(uap_metadata #>> '{platform_meta,smap,deleted_at}', '') = ''
"""
                ),
                {
                    "target_filter": json.dumps(
                        {"platform_meta": {"smap": {"target_id": target_id}}}
                    ),
                    "reason": reason or "stalker_flush",
                    "hidden_by": hidden_by or "ingest-srv",
                },
            )
            await session.commit()
        hidden_rows = int(result.rowcount or 0)
        self._response_cache.clear()
        self._timeout_cache.clear()
        return {
            "status": "ok",
            "target_id": target_id,
            "data_source_id": data_source_id,
            "hidden_rows": hidden_rows,
            "mart_refreshed": False,
        }

    async def _refresh_latest_mart_once(self) -> bool:
        if not self.db.engine:
            return False

        async with self.db.engine.connect() as raw_conn:
            conn = await raw_conn.execution_options(isolation_level="AUTOCOMMIT")
            lock_acquired = False
            try:
                lock_result = await conn.execute(
                    text("SELECT pg_try_advisory_lock(2026051007)")
                )
                lock_acquired = bool(lock_result.scalar())
                if not lock_acquired:
                    return False

                timeout_ms = max(
                    1_000, _env_int("ANALYTICS_FLUSH_REFRESH_TIMEOUT_MS", 10_000)
                )
                await conn.execute(text(f"SET statement_timeout = {timeout_ms}"))
                await conn.execute(
                    text("SELECT analysis.refresh_latest_post_insight()")
                )
                return True
            except Exception:
                return False
            finally:
                if lock_acquired:
                    try:
                        await conn.execute(
                            text("SELECT pg_advisory_unlock(2026051007)")
                        )
                    except Exception:
                        pass

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

    def _normalize_uuid_csv(self, value: str | None) -> tuple[str, ...]:
        if not value:
            return ()
        normalized: list[str] = []
        seen: set[str] = set()
        for item in str(value).split(","):
            candidate = item.strip()
            if not candidate or candidate in seen:
                continue
            self._validate_uuid(candidate)
            seen.add(candidate)
            normalized.append(candidate)
        return tuple(normalized[:100])

    def _normalize_keyword_csv(self, value: str | None) -> tuple[str, ...]:
        if not value:
            return ()
        normalized: list[str] = []
        seen: set[str] = set()
        for item in str(value).split(","):
            candidate = " ".join(item.strip().lower().split())
            if not candidate or candidate in seen:
                continue
            seen.add(candidate)
            normalized.append(candidate)
        return tuple(normalized[:20])

    def _normalize_content_type(self, value: str | None) -> str:
        raw = str(value or "all").strip().lower()
        aliases = {
            "mentions": "all",
            "mention": "all",
            "posts": "post",
            "videos": "post",
            "video": "post",
            "comments": "comment",
            "replies": "reply",
        }
        raw = aliases.get(raw, raw)
        return raw if raw in {"all", "post", "comment", "reply"} else "all"

    def _source_kind_pre_filters(
        self, source_kind: str, alias: str = "pi"
    ) -> list[str]:
        kind = self._normalize_source_kind(source_kind)
        source_expr = f"COALESCE({alias}.uap_metadata #>> '{{platform_meta,smap,source_kind}}', '')"
        if kind == "stalker":
            return [f"{source_expr} IN ('focused_page', 'focused_profile')"]
        if kind == "keyword":
            return [f"({source_expr} = '' OR {source_expr} = 'keyword_search')"]
        return []

    def _keyword_filter_expr(
        self, keywords: tuple[str, ...], alias: str = "pi"
    ) -> str | None:
        if not keywords:
            return None
        escaped_keywords = [self._escape(keyword.lower()) for keyword in keywords]
        values = ", ".join(f"'{keyword}'" for keyword in escaped_keywords)
        like_conditions = " OR ".join(
            f"LOWER(COALESCE({alias}.content, '')) LIKE '%{keyword}%'"
            for keyword in escaped_keywords
        )
        return (
            "("
            f"EXISTS (SELECT 1 FROM unnest(COALESCE({alias}.keywords, '{{}}')) AS scope_kw "
            f"WHERE LOWER(scope_kw) IN ({values}))"
            f" OR LOWER(COALESCE({alias}.uap_metadata #>> '{{crawl_keyword}}', '')) IN ({values})"
            f" OR {like_conditions}"
            ")"
        )

    def _content_type_expr(self, alias: str = "pi") -> str:
        depth_expr = f"COALESCE({alias}.uap_metadata #>> '{{hierarchy,depth}}', '')"
        doc_expr = f"LOWER(COALESCE({alias}.uap_metadata->>'doc_type', {alias}.uap_metadata->>'uap_type', ''))"
        url_expr = f"COALESCE({alias}.uap_metadata->>'url', '')"
        source_expr = f"COALESCE({alias}.source_id, '')"
        platform_expr = f"UPPER(COALESCE({alias}.platform, ''))"
        return (
            "CASE "
            f"WHEN {depth_expr} ~ '^[2-9]' OR {doc_expr} = 'reply' THEN 'reply' "
            f"WHEN {depth_expr} = '1' OR {doc_expr} = 'comment' "
            f"OR ({platform_expr} = 'YOUTUBE' AND ({url_expr} LIKE '%&lc=%' OR {url_expr} LIKE '%?lc=%' OR {source_expr} LIKE 'Ug%')) THEN 'comment' "
            f"WHEN {depth_expr} = '0' OR {doc_expr} IN ('post', 'video', 'news', 'feedback') THEN 'post' "
            "ELSE 'mention' END"
        )

    def _content_type_filter_expr(
        self, content_type: str, alias: str = "pi"
    ) -> str | None:
        kind = self._normalize_content_type(content_type)
        if kind == "all":
            return None
        return f"{self._content_type_expr(alias)} = '{kind}'"

    def _scope_pre_filters(
        self,
        scope: AnalyticsScope,
        include_content_type: bool = False,
        alias: str = "pi",
    ) -> list[str]:
        filters = [self._hidden_target_filter_expr(alias)]
        filters.extend(self._source_kind_pre_filters(scope.source_kind, alias))
        keyword_filter = self._keyword_filter_expr(scope.keywords, alias)
        if keyword_filter:
            filters.append(keyword_filter)
        if include_content_type:
            content_filter = self._content_type_filter_expr(scope.content_type, alias)
            if content_filter:
                filters.append(content_filter)
        return filters

    def _hidden_target_filter_expr(self, alias: str = "pi") -> str:
        return (
            f"COALESCE({alias}.uap_metadata #>> '{{platform_meta,smap,visibility}}', '') <> 'flushed' "
            f"AND COALESCE({alias}.uap_metadata #>> '{{platform_meta,smap,deleted_at}}', '') = ''"
            " AND NOT EXISTS ("
            "SELECT 1 FROM analysis.hidden_crawl_targets hct "
            f"WHERE hct.target_id::text = COALESCE({alias}.uap_metadata #>> '{{platform_meta,smap,target_id}}', '')"
            ")"
        )

    def _apply_relevance_filter(self, pre_filters: list[str] | None = None) -> bool:
        joined_filters = " ".join(pre_filters or [])
        return (
            "focused_page" not in joined_filters
            and "focused_profile" not in joined_filters
        )

    def _analytics_source_table(self) -> str:
        return (
            "analysis.latest_post_insight"
            if self._use_latest_mart
            else "analysis.post_insight"
        )

    def _has_source_url_expr(self, alias: str = "pi") -> str:
        return (
            "("
            f"COALESCE({alias}.uap_metadata->>'url', '') <> '' "
            f"OR COALESCE({alias}.uap_metadata->>'post_url', '') <> '' "
            f"OR COALESCE({alias}.uap_metadata->>'original_url', '') <> '' "
            f"OR COALESCE({alias}.uap_metadata->>'source_url', '') <> '' "
            f"OR COALESCE({alias}.uap_metadata->>'web_url', '') <> '' "
            f"OR COALESCE({alias}.uap_metadata->>'parent_post_url', '') <> '' "
            f"OR COALESCE({alias}.uap_metadata->>'comment_url', '') <> '' "
            f"OR COALESCE({alias}.uap_metadata->>'share_url', '') <> '' "
            f"OR COALESCE({alias}.uap_metadata->>'permalink_url', '') <> '' "
            f"OR COALESCE({alias}.uap_metadata #>> '{{platform_meta,youtube,parent_url}}', '') <> '' "
            f"OR COALESCE({alias}.uap_metadata #>> '{{platform_meta,youtube,video_url}}', '') <> '' "
            f"OR COALESCE({alias}.uap_metadata #>> '{{platform_meta,tiktok,video_url}}', '') <> '' "
            f"OR COALESCE({alias}.uap_metadata #>> '{{platform_meta,facebook,post_url}}', '') <> '' "
            f"OR COALESCE({alias}.uap_metadata #>> '{{platform_meta,facebook,permalink_url}}', '') <> ''"
            ")"
        )

    def _business_signal_expr(self, alias: str = "pi") -> str:
        return (
            f"COALESCE({alias}.content, '') ~* "
            "'(ahamove|grab|lalamove|be|xanh sm|giao hàng|shipper|tài xế|đơn hàng|đặt xe|vận chuyển|thu hộ|cod|tanca|hrm|crm|nhân sự|chấm công|bảng lương|tiền lương|sales|marketing|chiến dịch|thương hiệu|dịch vụ|khách hàng|tổng đài|hỗ trợ)'"
        )

    def _service_intent_expr(self, alias: str = "pi") -> str:
        return (
            f"COALESCE({alias}.content, '') ~* "
            "'(trải nghiệm|review|đánh giá|phản hồi|phàn nàn|khiếu nại|bức xúc|hài lòng|không hài lòng|lỗi|tệ|ổn|chậm|trễ|delay|hủy|huỷ|hoàn tiền|refund|đối soát|đơn hàng|đơn|book|đặt|app|ứng dụng|tài xế|shipper|driver|đối tác|chạy|thu nhập|kiếm|lương|phạt|thưởng|đăng ký|hỗ trợ|tổng đài|khách hàng|cước|giá cước|cod|thu hộ|giao hàng|vận chuyển|dịch vụ)'"
        )

    def _marketplace_noise_expr(self, alias: str = "pi") -> str:
        return (
            f"COALESCE({alias}.content, '') ~* "
            "'(zalo|inbox|(^|[^[:alnum:]_])ib([^[:alnum:]_]|$)|chốt đơn|menu|shop|có sẵn|hàng có sẵn|hàng_có_sẵn|đồng giá|sỉ|lẻ|mỹ phẩm|serum|son|trái cây|bánh|chậu|cây|lồng đèn|túi|áo khoác|ship toàn quốc|ship từ|phí ship|ngoại ô xa phí|bao check|bán hàng|cần ra đi|em mời khách|(^|[^[:alnum:]_])[0-9]{2,4}k([^[:alnum:]_]|$))'"
        )

    def _hard_noise_expr(self, alias: str = "pi") -> str:
        return (
            f"COALESCE({alias}.content, '') ~* "
            "'(youtube\\.com/shopcollection|bộ đồ nghề|zalo|chuyên bán|menu trái cây|bánh cuốn|serum|cọ gấu|hàng có sẵn|hàng_có_sẵn|định danh chủ|cà mau.*đăng ký|đăng ký.*cà mau|(^|[^0-9])0[0-9]{8,10}([^0-9]|$))'"
        )

    def _quality_guard_expr(self, alias: str = "pi") -> str:
        marketplace_noise_expr = self._marketplace_noise_expr(alias)
        hard_noise_expr = self._hard_noise_expr(alias)
        service_intent_expr = self._service_intent_expr(alias)
        return f"(NOT {hard_noise_expr} AND (NOT {marketplace_noise_expr} OR {service_intent_expr}))"

    def _source_quality_filter_expr(self, alias: str = "pi") -> str:
        """Keep default dashboard reads focused on traceable, project-related data.

        Older indexed rows can have a soft business relevance score but no URL,
        crawl keyword, ontology keyword, or focused-source marker. URL alone is
        not enough because unrelated viral posts can still carry permalinks.
        Stalker/focused rows remain visible even without permalinks.
        """
        source_expr = f"COALESCE({alias}.uap_metadata #>> '{{platform_meta,smap,source_kind}}', '')"
        has_url_expr = self._has_source_url_expr(alias)
        business_signal_expr = self._business_signal_expr(alias)
        quality_guard_expr = self._quality_guard_expr(alias)
        candidate_expr = (
            "("
            f"(COALESCE({alias}.uap_metadata #>> '{{crawl_keyword}}', '') <> '' AND {business_signal_expr}) "
            f"OR (COALESCE(array_length({alias}.keywords, 1), 0) > 0 AND {business_signal_expr}) "
            f"OR ({has_url_expr} AND ({business_signal_expr} OR {alias}.business_relevance_score >= 0.72))"
            ")"
        )
        return (
            "("
            f"{source_expr} IN ('focused_page', 'focused_profile') "
            f"OR ({candidate_expr} AND {quality_guard_expr})"
            ")"
        )

    def _base_cte(
        self, project_ids: list[str], pre_filters: list[str] | None = None
    ) -> str:
        quoted_ids = ", ".join(
            f"'{self._escape(project_id)}'" for project_id in project_ids
        )
        identity_expr = self._source_identity_expr("pi")
        extra_where = "\n".join(
            f"    AND {condition}" for condition in (pre_filters or [])
        )
        apply_relevance = self._apply_relevance_filter(pre_filters)
        relevance_where = (
            "    AND pi.business_relevance_score >= 0.45" if apply_relevance else ""
        )
        quality_where = (
            f"    AND {self._source_quality_filter_expr('pi')}"
            if self._source_quality_gate and apply_relevance
            else ""
        )
        source_table = self._analytics_source_table()
        if self._use_latest_mart:
            # The mart deduplicates per (project_id, source_identity), but the
            # same TikTok comment / FB post often gets ingested under several
            # projects within the same campaign. Without a second pass, every
            # cross-project shadow row leaks into the page and the user sees
            # the same author repeat across pagination.
            return f"""
WITH deduped_post_insight AS (
  SELECT DISTINCT ON (
    COALESCE(NULLIF(UPPER(pi.platform), ''), 'UNKNOWN'),
    {identity_expr}
  )
    pi.*
  FROM {source_table} pi
  WHERE project_id IN ({quoted_ids})
{extra_where}
  ORDER BY
    COALESCE(NULLIF(UPPER(pi.platform), ''), 'UNKNOWN'),
    {identity_expr},
    pi.engagement_score DESC NULLS LAST,
    pi.id DESC
)
"""
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
{quality_where}
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

    def _posts_base_cte(
        self, project_ids: list[str], pre_filters: list[str] | None = None
    ) -> str:
        quoted_ids = ", ".join(
            f"'{self._escape(project_id)}'" for project_id in project_ids
        )
        identity_expr = self._source_identity_expr("pi")
        extra_where = "\n".join(
            f"    AND {condition}" for condition in (pre_filters or [])
        )
        apply_relevance = self._apply_relevance_filter(pre_filters)
        relevance_where = (
            "    AND pi.business_relevance_score >= 0.45" if apply_relevance else ""
        )
        quality_where = (
            f"    AND {self._source_quality_filter_expr('pi')}"
            if self._source_quality_gate and apply_relevance
            else ""
        )
        source_table = self._analytics_source_table()
        if self._use_latest_mart:
            # Cross-project dedup: the same comment/post can sit under several
            # projects in one campaign, and the mart only dedupes within a
            # project. DISTINCT ON keeps the highest-engagement row so the
            # paginated Insight list stops repeating the same author.
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
  FROM {source_table} pi
  WHERE project_id IN ({quoted_ids})
{extra_where}
  ORDER BY
    COALESCE(NULLIF(UPPER(pi.platform), ''), 'UNKNOWN'),
    {identity_expr},
    pi.engagement_score DESC NULLS LAST,
    pi.id DESC
),
"""
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
{relevance_where}
{quality_where}
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
