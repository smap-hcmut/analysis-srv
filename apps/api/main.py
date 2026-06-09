from __future__ import annotations

import asyncio
import logging
import os
import time
from contextlib import asynccontextmanager, suppress
from pathlib import Path

import yaml

from fastapi import FastAPI, Query, Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel
from sqlalchemy import text

from internal.http.analytics_service import AnalyticsService
from internal.http.errors import APIError
from internal.http.project_client import build_project_service_client
from internal.observability.metrics import PROMETHEUS_AVAILABLE
from internal.model.constant import (
    LOGGER_COLORIZE,
    LOGGER_ENABLE_CONSOLE,
    LOGGER_ENABLE_TRACE_ID,
    LOGGER_SERVICE_NAME,
    POSTGRES_SCHEMA,
)
from pkg.logger.logger import Logger, LoggerConfig
from pkg.postgre.postgres import PostgresDatabase
from pkg.postgre.type import PostgresConfig


class APIDependencies:
    def __init__(
        self,
        logger: Logger,
        db: PostgresDatabase,
        analytics_query_timeout_ms: int,
        mart_refresh_seconds: int,
        mart_refresh_timeout_ms: int,
    ):
        self.logger = logger
        self.db = db
        self.analytics_query_timeout_ms = analytics_query_timeout_ms
        self.mart_refresh_seconds = mart_refresh_seconds
        self.mart_refresh_timeout_ms = mart_refresh_timeout_ms
        self.ready = True
        self._ready_cache_value: bool = True
        self._ready_cache_until: float = 0.0
        self._ready_cache_ttl: float = 5.0
        self._mart_refresh_failed_until: float = 0.0

    async def ready_check(self) -> bool:
        now = time.time()
        if now < self._ready_cache_until:
            return self._ready_cache_value
        ok = await self.db.health_check()
        self._ready_cache_value = ok
        # cache successes longer than failures so probes don't hammer DB on bad days either
        self._ready_cache_until = now + (self._ready_cache_ttl if ok else 1.0)
        return ok


def _load_yaml_config() -> dict:
    config_path = Path("config/config.yaml")
    if not config_path.exists():
        return {}

    with config_path.open("r", encoding="utf-8") as file:
        return yaml.safe_load(file) or {}


def _env_or_config(env_key: str, config: dict, path: tuple[str, ...], default):
    value = os.getenv(env_key)
    if value is not None:
        return value

    current = config
    for part in path:
        if not isinstance(current, dict):
            return default
        current = current.get(part)

    return current if current is not None else default


async def init_api_dependencies() -> APIDependencies:
    config = _load_yaml_config()
    log_level = _env_or_config("ANALYTICS_LOGGING_LEVEL", config, ("logging", "level"), "INFO")
    json_output = _env_or_config("ANALYTICS_LOGGING_JSON_OUTPUT", config, ("logging", "json_output"), False)
    database_url = _env_or_config("ANALYTICS_DATABASE_URL", config, ("database", "url"), "")
    pool_size = int(_env_or_config("ANALYTICS_DATABASE_POOL_SIZE", config, ("database", "pool_size"), 10))
    max_overflow = int(_env_or_config("ANALYTICS_DATABASE_MAX_OVERFLOW", config, ("database", "max_overflow"), 5))
    statement_timeout_ms = int(
        _env_or_config("ANALYTICS_DATABASE_STATEMENT_TIMEOUT_MS", config, ("database", "statement_timeout_ms"), 25_000)
    )
    idle_in_tx_timeout_ms = int(
        _env_or_config("ANALYTICS_DATABASE_IDLE_TX_TIMEOUT_MS", config, ("database", "idle_in_transaction_timeout_ms"), 30_000)
    )
    query_timeout_ms = int(_env_or_config("ANALYTICS_QUERY_TIMEOUT_MS", config, ("database", "query_timeout_ms"), 25_000))
    mart_refresh_seconds = int(
        _env_or_config("ANALYTICS_MART_REFRESH_SECONDS", config, ("database", "mart_refresh_seconds"), 300)
    )
    mart_refresh_timeout_ms = int(
        _env_or_config("ANALYTICS_MART_REFRESH_TIMEOUT_MS", config, ("database", "mart_refresh_timeout_ms"), 240_000)
    )
    if statement_timeout_ms > 0:
        query_timeout_ms = min(query_timeout_ms, statement_timeout_ms)
    if query_timeout_ms <= 0:
        query_timeout_ms = 25_000
    if mart_refresh_seconds < 0:
        mart_refresh_seconds = 0
    if mart_refresh_timeout_ms <= 0:
        mart_refresh_timeout_ms = 240_000

    if not database_url:
        raise RuntimeError("ANALYTICS_DATABASE_URL is required")

    logger = Logger(
        LoggerConfig(
            level=log_level,
            enable_console=LOGGER_ENABLE_CONSOLE,
            colorize=LOGGER_COLORIZE,
            service_name=LOGGER_SERVICE_NAME,
            enable_trace_id=LOGGER_ENABLE_TRACE_ID,
            json_output=str(json_output).lower() in {"true", "1", "yes"},
        )
    )
    db = PostgresDatabase(
        PostgresConfig(
            database_url=database_url,
            schema=POSTGRES_SCHEMA,
            pool_size=pool_size,
            max_overflow=max_overflow,
            statement_timeout_ms=statement_timeout_ms,
            idle_in_transaction_timeout_ms=idle_in_tx_timeout_ms,
        )
    )
    if not await db.health_check():
        raise RuntimeError("analysis-api database health check failed")
    return APIDependencies(
        logger=logger,
        db=db,
        analytics_query_timeout_ms=query_timeout_ms,
        mart_refresh_seconds=mart_refresh_seconds,
        mart_refresh_timeout_ms=mart_refresh_timeout_ms,
    )


async def _list_projects_to_refresh(deps: APIDependencies) -> list[str]:
    """Return project_ids whose rollups should be refreshed this tick.

    Combines projects that already have rollup rows (so the loop keeps them
    warm) with projects that received fresh `analysis.post_insight` rows in
    the recent window (so new campaigns get their first rollup quickly).
    Both halves of the union ride on small indexes, so the lookup cost is
    bounded regardless of how big `analysis.post_insight` becomes.
    """
    if not deps.db.engine:
        return []
    # Discovery prefers the rollup tables (cheap aggregates, always
    # indexable). Falls back to a recent post_insight scan only when the
    # rollups are empty — that path needs an index on analyzed_at and
    # otherwise degrades to a parallel seq scan over 8M+ rows.
    union_sql = text(
        """
        SELECT DISTINCT project_id FROM analysis.kpi_daily
        UNION
        SELECT DISTINCT project_id FROM analysis.posts_recent_top
        UNION
        SELECT DISTINCT project_id FROM analysis.metrics_daily
        """
    )
    async with deps.db.engine.connect() as raw_conn:
        conn = await raw_conn.execution_options(isolation_level="AUTOCOMMIT")
        await conn.execute(text("SET statement_timeout = 15000"))
        result = await conn.execute(union_sql)
        rows = result.fetchall()
    project_ids = [str(row[0]) for row in rows if row and row[0]]

    # Only fall back to scanning post_insight when no rollup row exists at
    # all — this only fires the first time a project arrives, and afterwards
    # the rollup-driven loop keeps the project in the working set.
    if project_ids:
        return project_ids

    window_seconds = max(60, int(deps.mart_refresh_seconds * 4 or 3600))
    fallback_sql = text(
        f"""
        SELECT DISTINCT project_id
          FROM analysis.post_insight
         WHERE analyzed_at > now() - interval '{window_seconds} seconds'
        """
    )
    async with deps.db.engine.connect() as raw_conn:
        conn = await raw_conn.execution_options(isolation_level="AUTOCOMMIT")
        await conn.execute(text("SET statement_timeout = 30000"))
        result = await conn.execute(fallback_sql)
        rows = result.fetchall()
    return [str(row[0]) for row in rows if row and row[0]]


async def _refresh_project_rollups(deps: APIDependencies, project_id: str) -> None:
    """Refresh a single project's rollups via the SQL entry point.

    The SQL function holds a per-project advisory lock so overlapping loop
    iterations are a no-op rather than a stampede. `statement_timeout` is
    capped per-project: each call processes one project's slice of
    `post_insight`, which is bounded by the project's own data volume.

    Falls back to direct DELETE+INSERT on `posts_recent_top` and
    `metrics_daily` when `analysis.refresh_project_rollups` is not present
    (e.g. migration 015 not yet applied). The fallback skips `kpi_daily`
    because the analysis-api role typically lacks write privileges there;
    kpi_daily refresh requires the SQL function to be installed.
    """
    if not deps.db.engine:
        return
    per_project_timeout_ms = max(15_000, min(int(deps.mart_refresh_timeout_ms or 60_000), 120_000))
    async with deps.db.engine.connect() as raw_conn:
        conn = await raw_conn.execution_options(isolation_level="AUTOCOMMIT")
        await conn.execute(text(f"SET statement_timeout = {per_project_timeout_ms}"))
        await conn.execute(text("SET lock_timeout = '5s'"))
        try:
            await conn.execute(
                text("SELECT analysis.refresh_project_rollups(:project_id)"),
                {"project_id": project_id},
            )
            return
        except Exception as exc:
            message = str(exc).lower()
            missing = (
                "does not exist" in message
                or "undefinedfunction" in message
                or "function analysis.refresh_project_rollups" in message
            )
            if not missing:
                raise
        # Fallback path: per-project refresh without the SQL function. Kept
        # tight to the tables analysis_prod owns so it works before migration
        # 015 lands.
        await conn.execute(
            text("DELETE FROM analysis.posts_recent_top WHERE project_id = :pid"),
            {"pid": project_id},
        )
        await conn.execute(
            text(
                """
                INSERT INTO analysis.posts_recent_top (
                  project_id, uap_id, source_id, platform, content_excerpt, author,
                  content_created_at, overall_sentiment, sentiment_score,
                  engagement_score, reach_estimate, url, uap_metadata, refreshed_at
                )
                SELECT
                  project_id,
                  COALESCE(uap_metadata->>'uap_id', source_id) AS uap_id,
                  source_id,
                  COALESCE(NULLIF(UPPER(platform), ''), 'UNKNOWN') AS platform,
                  LEFT(content, 320) AS content_excerpt,
                  COALESCE(
                    uap_metadata->>'author_display_name',
                    uap_metadata->>'author_username',
                    uap_metadata->>'author'
                  ) AS author,
                  content_created_at,
                  overall_sentiment,
                  overall_sentiment_score AS sentiment_score,
                  engagement_score,
                  reach_estimate,
                  COALESCE(
                    uap_metadata->>'post_url',
                    uap_metadata->>'url',
                    uap_metadata->>'permalink_url',
                    uap_metadata->>'original_url'
                  ) AS url,
                  uap_metadata,
                  NOW()
                FROM (
                  SELECT *,
                         ROW_NUMBER() OVER (
                           PARTITION BY project_id
                           ORDER BY content_created_at DESC NULLS LAST,
                                    engagement_score DESC NULLS LAST
                         ) AS rn
                  FROM (
                    SELECT DISTINCT ON (
                      COALESCE(NULLIF(UPPER(platform), ''), 'UNKNOWN'),
                      COALESCE(
                        NULLIF(source_id, ''),
                        NULLIF(uap_metadata->>'post_id', ''),
                        NULLIF(uap_metadata->>'comment_id', ''),
                        NULLIF(uap_metadata->>'video_id', ''),
                        NULLIF(uap_metadata->>'url', ''),
                        id::text
                      )
                    ) *
                    FROM analysis.post_insight
                    WHERE project_id = :pid
                      AND content_created_at IS NOT NULL
                      AND (
                        COALESCE(business_relevance_score, 0) >= 0.30
                        OR COALESCE(uap_metadata #>> '{platform_meta,smap,source_kind}', '') IN ('focused_page', 'focused_profile')
                      )
                    ORDER BY
                      COALESCE(NULLIF(UPPER(platform), ''), 'UNKNOWN'),
                      COALESCE(
                        NULLIF(source_id, ''),
                        NULLIF(uap_metadata->>'post_id', ''),
                        NULLIF(uap_metadata->>'comment_id', ''),
                        NULLIF(uap_metadata->>'video_id', ''),
                        NULLIF(uap_metadata->>'url', ''),
                        id::text
                      ),
                      COALESCE(updated_at, analyzed_at, ingested_at, created_at) DESC NULLS LAST,
                      created_at DESC NULLS LAST,
                      id DESC
                  ) deduped
                ) ranked
                WHERE ranked.rn <= 1000
                """
            ),
            {"pid": project_id},
        )
        await conn.execute(
            text("DELETE FROM analysis.metrics_daily WHERE project_id = :pid"),
            {"pid": project_id},
        )
        await conn.execute(
            text(
                """
                INSERT INTO analysis.metrics_daily (
                  project_id, bucket_date, platform, sentiment,
                  mentions, sentiment_score, engagement_sum, reach_sum, refreshed_at
                )
                SELECT
                  project_id,
                  DATE_TRUNC('day', content_created_at)::DATE AS bucket_date,
                  COALESCE(NULLIF(UPPER(platform), ''), 'UNKNOWN') AS platform,
                  COALESCE(NULLIF(UPPER(overall_sentiment), ''), 'UNKNOWN') AS sentiment,
                  COUNT(*) AS mentions,
                  AVG(COALESCE(overall_sentiment_score, 0)) AS sentiment_score,
                  SUM(COALESCE(engagement_score, 0)) AS engagement_sum,
                  SUM(COALESCE(reach_estimate, 0)) AS reach_sum,
                  NOW()
                FROM (
                  SELECT DISTINCT ON (
                    COALESCE(NULLIF(UPPER(platform), ''), 'UNKNOWN'),
                    COALESCE(
                      NULLIF(source_id, ''),
                      NULLIF(uap_metadata->>'post_id', ''),
                      NULLIF(uap_metadata->>'comment_id', ''),
                      NULLIF(uap_metadata->>'video_id', ''),
                      NULLIF(uap_metadata->>'url', ''),
                      id::text
                    )
                  )
                    project_id,
                    content_created_at,
                    platform,
                    overall_sentiment,
                    overall_sentiment_score,
                    engagement_score,
                    reach_estimate
                  FROM analysis.post_insight
                  WHERE project_id = :pid
                    AND content_created_at IS NOT NULL
                    AND (
                      COALESCE(business_relevance_score, 0) >= 0.30
                      OR COALESCE(uap_metadata #>> '{platform_meta,smap,source_kind}', '') IN ('focused_page', 'focused_profile')
                    )
                  ORDER BY
                    COALESCE(NULLIF(UPPER(platform), ''), 'UNKNOWN'),
                    COALESCE(
                      NULLIF(source_id, ''),
                      NULLIF(uap_metadata->>'post_id', ''),
                      NULLIF(uap_metadata->>'comment_id', ''),
                      NULLIF(uap_metadata->>'video_id', ''),
                      NULLIF(uap_metadata->>'url', ''),
                      id::text
                    ),
                    COALESCE(updated_at, analyzed_at, ingested_at, created_at) DESC NULLS LAST,
                    created_at DESC NULLS LAST,
                    id DESC
                ) deduped
                GROUP BY
                  project_id,
                  DATE_TRUNC('day', content_created_at)::DATE,
                  COALESCE(NULLIF(UPPER(platform), ''), 'UNKNOWN'),
                  COALESCE(NULLIF(UPPER(overall_sentiment), ''), 'UNKNOWN')
                """
            ),
            {"pid": project_id},
        )


async def _refresh_project_rollups_tick(deps: APIDependencies) -> None:
    """Run one refresh tick across every project that needs rollup updates.

    Projects are refreshed in parallel batches so a 19-project tick fits
    in ~30 s instead of the ~220 s the sequential loop took. The
    concurrency cap keeps the burst from saturating PostgreSQL connection
    slots — kine shares this server and the apiserver VIP drops when
    kine writes back up. A per-project failure does not abort the tick.
    """
    if not deps.db.engine:
        return
    now = time.time()
    if now < deps._mart_refresh_failed_until:
        return
    try:
        project_ids = await _list_projects_to_refresh(deps)
    except Exception as exc:  # pragma: no cover - operational guardrail
        deps._mart_refresh_failed_until = time.time() + max(60, min(600, deps.mart_refresh_seconds))
        deps.logger.warning(f"analysis-api rollup discovery failed: {exc}")
        return

    if not project_ids:
        deps.logger.info("analysis-api rollup tick: no active projects")
        return

    started = time.perf_counter()
    concurrency = max(1, int(os.getenv("ANALYTICS_MART_REFRESH_CONCURRENCY", "4")))
    semaphore = asyncio.Semaphore(concurrency)
    failed_projects: list[str] = []
    succeeded_count = 0

    async def _run_one(pid: str) -> None:
        nonlocal succeeded_count
        async with semaphore:
            try:
                await _refresh_project_rollups(deps, pid)
                succeeded_count += 1
            except Exception as exc:  # pragma: no cover - operational guardrail
                failed_projects.append(pid)
                deps.logger.warning(
                    f"analysis-api rollup refresh failed for project {pid}: {exc}"
                )

    await asyncio.gather(*(_run_one(pid) for pid in project_ids))
    succeeded = succeeded_count
    elapsed = time.perf_counter() - started
    deps.logger.info(
        "analysis-api rollup tick complete: "
        f"projects={len(project_ids)} succeeded={succeeded} "
        f"failed={len(failed_projects)} duration_s={elapsed:.2f}"
    )


async def _per_project_rollup_loop(deps: APIDependencies) -> None:
    if deps.mart_refresh_seconds <= 0:
        return
    # Initial delay so a fresh pod doesn't fight the readiness probe with a
    # long refresh on the very first tick after a deploy.
    await asyncio.sleep(min(deps.mart_refresh_seconds, 30))
    while True:
        await _refresh_project_rollups_tick(deps)
        await asyncio.sleep(deps.mart_refresh_seconds)


@asynccontextmanager
async def lifespan(app: FastAPI):
    deps = await init_api_dependencies()
    project_client = build_project_service_client()
    mart_task = asyncio.create_task(_per_project_rollup_loop(deps))
    app.state.deps = deps
    app.state.project_client = project_client
    app.state.analytics = AnalyticsService(
        db=deps.db,
        project_client=project_client,
        query_timeout_ms=deps.analytics_query_timeout_ms,
    )
    try:
        yield
    finally:
        mart_task.cancel()
        with suppress(asyncio.CancelledError):
            await mart_task
        await project_client.close()
        if getattr(deps, "db", None):
            await deps.db.close()


app = FastAPI(title="analysis-api", lifespan=lifespan)


# Force the browser / SWR / any HTTP cache in front of analysis-api to
# re-fetch every Insight dashboard request. The backend keeps its own
# short response cache for hot paths, but if the client caches by URL
# the user sees stuck numbers even after a hard refresh — that was the
# root cause of the "vẫn 3.2K" complaint on 2026-06-09.
@app.middleware("http")
async def _no_browser_cache(request: Request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/api/v1/analytics"):
        response.headers["Cache-Control"] = "no-store, max-age=0, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


# Prometheus metrics endpoint. Mounted only when prometheus_client is installed
# (graceful no-op otherwise). Counters are wired through internal.observability
# and updated by request middleware below.
if PROMETHEUS_AVAILABLE:
    from prometheus_client import (
        CONTENT_TYPE_LATEST,
        REGISTRY,
        Counter,
        Histogram,
        generate_latest,
    )

    # The module is imported twice: once as __main__ when the deployment runs
    # `python -m apps.api.main`, then again by uvicorn as `apps.api.main` so it
    # can locate the `app` symbol. Without this guard the second import double-
    # registers the same time series and crashes startup with "Duplicated
    # timeseries in CollectorRegistry".
    def _get_or_create_counter(name: str, doc: str, labels: list[str]) -> Counter:
        existing = REGISTRY._names_to_collectors.get(name)
        if existing is not None:
            return existing
        return Counter(name, doc, labels)

    def _get_or_create_histogram(
        name: str, doc: str, labels: list[str], buckets: tuple[float, ...]
    ) -> Histogram:
        existing = REGISTRY._names_to_collectors.get(name)
        if existing is not None:
            return existing
        return Histogram(name, doc, labels, buckets=buckets)

    _http_requests_total = _get_or_create_counter(
        "analysis_api_http_requests_total",
        "Total HTTP requests received by analysis-api",
        ["method", "route", "status"],
    )
    _http_request_duration_seconds = _get_or_create_histogram(
        "analysis_api_http_request_duration_seconds",
        "HTTP request duration in seconds",
        ["method", "route"],
        (0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30, 60, 120),
    )

    @app.middleware("http")
    async def _prometheus_middleware(request: Request, call_next):
        # Skip /metrics itself so scrapes don't show up as application traffic.
        if request.url.path == "/metrics":
            return await call_next(request)
        # Use the route template (e.g. "/api/v1/analytics/posts") instead of
        # the concrete path to keep cardinality bounded.
        route_template = request.scope.get("route").path if request.scope.get("route") else request.url.path
        start = time.perf_counter()
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        except Exception:
            status_code = 500
            raise
        finally:
            elapsed = time.perf_counter() - start
            _http_requests_total.labels(
                method=request.method,
                route=route_template,
                status=str(status_code),
            ).inc()
            _http_request_duration_seconds.labels(
                method=request.method,
                route=route_template,
            ).observe(elapsed)

    @app.get("/metrics", include_in_schema=False)
    async def metrics() -> Response:
        return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


class HiddenCrawlTargetRequest(BaseModel):
    target_id: str
    data_source_id: str = ""
    reason: str = "stalker_flush"
    hidden_by: str = "ingest-srv"


def _require_internal_key(request: Request) -> JSONResponse | None:
    expected = os.getenv("INTERNAL_KEY") or os.getenv("INTERNAL_INTERNAL_KEY")
    if not expected:
        return JSONResponse(status_code=503, content={"error": "internal key is not configured"})
    received = request.headers.get("x-internal-key") or request.headers.get("x-smap-internal-key")
    if received != expected:
        return JSONResponse(status_code=403, content={"error": "forbidden"})
    return None


class _ProbeAccessLogFilter(logging.Filter):
    """Drop uvicorn access log lines for /health and /ready to keep logs useful under load."""

    _PROBE_PATHS = ('"GET /health ', '"GET /ready ', "GET /health ", "GET /ready ")

    def filter(self, record: logging.LogRecord) -> bool:  # noqa: D401
        try:
            message = record.getMessage()
        except Exception:
            return True
        return not any(p in message for p in self._PROBE_PATHS)


logging.getLogger("uvicorn.access").addFilter(_ProbeAccessLogFilter())


@app.exception_handler(APIError)
async def api_error_handler(_request: Request, exc: APIError):
    return JSONResponse(status_code=exc.status_code, content={"error": exc.message})


@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, exc: Exception):
    deps = getattr(request.app.state, "deps", None)
    if deps and getattr(deps, "logger", None):
        deps.logger.error(f"analysis-api error: {exc}")
    # Translate Postgres statement_timeout (asyncpg QueryCanceledError, surfaced
    # by SQLAlchemy as DBAPIError with pgcode 57014) into a clear 504 instead
    # of a generic 500. This keeps the UI from showing scary stack traces and
    # signals the caller that retrying with a smaller scope may succeed.
    pgcode = getattr(getattr(exc, "orig", None), "sqlstate", None) or getattr(exc, "pgcode", None)
    if pgcode == "57014" or "statement timeout" in str(exc).lower() or "QueryCanceledError" in type(exc).__name__:
        return JSONResponse(
            status_code=504,
            content={"error": "analytics query exceeded server time limit"},
        )
    return JSONResponse(status_code=500, content={"error": str(exc) or "Internal server error"})


@app.get("/health")
async def health(request: Request):
    deps = getattr(request.app.state, "deps", None)
    return JSONResponse(status_code=200, content={"status": "ok" if deps and getattr(deps, "ready", False) else "starting"})


@app.get("/ready")
async def ready(request: Request):
    deps: APIDependencies = request.app.state.deps
    db_ok = await deps.ready_check()
    status = 200 if db_ok else 503
    return JSONResponse(status_code=status, content={"status": "ok" if db_ok else "degraded"})


@app.get("/api/v1/analytics/kpis")
async def get_kpis(
    request: Request,
    campaignId: str,
    sourceKind: str = "all",
    projectIds: str = "",
    keywords: str = "",
):
    return await request.app.state.analytics.get_kpis(campaignId, sourceKind, projectIds, keywords)


@app.get("/api/v1/analytics/platforms")
async def get_platforms(
    request: Request,
    campaignId: str,
    sourceKind: str = "all",
    projectIds: str = "",
    keywords: str = "",
):
    return await request.app.state.analytics.get_platforms(campaignId, sourceKind, projectIds, keywords)


@app.get("/api/v1/analytics/sentiment")
async def get_sentiment(
    request: Request,
    campaignId: str,
    sourceKind: str = "all",
    projectIds: str = "",
    keywords: str = "",
):
    return await request.app.state.analytics.get_sentiment(campaignId, sourceKind, projectIds, keywords)


@app.get("/api/v1/analytics/keywords")
async def get_keywords(
    request: Request,
    campaignId: str,
    limit: int = Query(default=50, ge=1, le=100),
    sourceKind: str = "all",
    projectIds: str = "",
    keywords: str = "",
):
    return await request.app.state.analytics.get_keywords(campaignId, limit, sourceKind, projectIds, keywords)


@app.get("/api/v1/analytics/posts")
async def get_posts(
    request: Request,
    campaignId: str,
    platform: str = "all",
    sentiment: str = "all",
    sort: str = "engagement",
    limit: int = Query(default=30, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    sourceKind: str = "all",
    projectIds: str = "",
    keywords: str = "",
    contentType: str = "all",
):
    return await request.app.state.analytics.get_posts(
        campaignId,
        platform,
        sentiment,
        sort,
        limit,
        offset,
        sourceKind,
        projectIds,
        keywords,
        contentType,
    )


@app.get("/api/v1/analytics/posts/export")
async def export_posts(
    request: Request,
    campaignId: str,
    format: str = "csv",
    platform: str = "all",
    sentiment: str = "all",
    sort: str = "engagement",
    sourceKind: str = "all",
    projectIds: str = "",
    keywords: str = "",
    contentType: str = "all",
):
    export = await request.app.state.analytics.export_posts(
        campaignId,
        format,
        platform,
        sentiment,
        sort,
        sourceKind,
        projectIds,
        keywords,
        contentType,
    )
    return Response(
        content=export["body"],
        media_type=export["media_type"],
        headers={
            "Content-Disposition": f'attachment; filename="{export["filename"]}"',
            "X-Export-Returned": str(export["returned"]),
            "X-Export-Total": str(export["total"]),
        },
    )


@app.get("/api/v1/analytics/project-stats")
async def get_project_stats(
    request: Request,
    campaignId: str,
    sourceKind: str = "all",
    projectIds: str = "",
    keywords: str = "",
):
    return await request.app.state.analytics.get_project_stats(campaignId, sourceKind, projectIds, keywords)


@app.get("/api/v1/analytics/heap")
async def get_heap(
    request: Request,
    campaignId: str,
    sourceKind: str = "all",
    projectIds: str = "",
    keywords: str = "",
):
    return await request.app.state.analytics.get_heap(campaignId, sourceKind, projectIds, keywords)


@app.post("/api/v1/internal/analytics/hidden-crawl-targets")
async def hide_crawl_target(request: Request, payload: HiddenCrawlTargetRequest):
    auth_error = _require_internal_key(request)
    if auth_error is not None:
        return auth_error
    result = await request.app.state.analytics.hide_crawl_target(
        payload.target_id,
        payload.data_source_id,
        payload.reason,
        payload.hidden_by,
    )
    return result


def run():
    import uvicorn

    host = os.getenv("ANALYTICS_API_HOST", "0.0.0.0")
    port = int(os.getenv("ANALYTICS_API_PORT", "8080"))
    uvicorn_log_level = os.getenv("ANALYTICS_UVICORN_LOG_LEVEL", "warning").strip().lower() or "warning"
    access_log_enabled = os.getenv("ANALYTICS_UVICORN_ACCESS_LOG", "false").strip().lower() in {"1", "true", "yes", "on"}
    uvicorn.run(
        "apps.api.main:app",
        host=host,
        port=port,
        reload=False,
        log_level=uvicorn_log_level,
        access_log=access_log_enabled,
    )


if __name__ == "__main__":
    run()
