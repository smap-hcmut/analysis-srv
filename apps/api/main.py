from __future__ import annotations

import asyncio
import logging
import os
import time
from contextlib import asynccontextmanager, suppress
from pathlib import Path

import yaml

from fastapi import FastAPI, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text

from internal.http.analytics_service import AnalyticsService
from internal.http.errors import APIError
from internal.http.project_client import build_project_service_client
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
    ):
        self.logger = logger
        self.db = db
        self.analytics_query_timeout_ms = analytics_query_timeout_ms
        self.mart_refresh_seconds = mart_refresh_seconds
        self.ready = True
        self._ready_cache_value: bool = True
        self._ready_cache_until: float = 0.0
        self._ready_cache_ttl: float = 5.0

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
    if statement_timeout_ms > 0:
        query_timeout_ms = min(query_timeout_ms, statement_timeout_ms)
    if query_timeout_ms <= 0:
        query_timeout_ms = 25_000
    if mart_refresh_seconds < 0:
        mart_refresh_seconds = 0

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
    )


async def _refresh_latest_post_insight_mart(deps: APIDependencies) -> None:
    """Refresh the dashboard mart without blocking app startup or requests."""
    if not deps.db.engine:
        return

    async with deps.db.engine.connect() as raw_conn:
        conn = await raw_conn.execution_options(isolation_level="AUTOCOMMIT")
        lock_acquired = False
        try:
            lock_result = await conn.execute(text("SELECT pg_try_advisory_lock(2026051007)"))
            lock_acquired = bool(lock_result.scalar())
            if not lock_acquired:
                return

            await conn.execute(text("SET statement_timeout = '180s'"))
            await conn.execute(text("SELECT analysis.refresh_latest_post_insight()"))
        except Exception as exc:  # pragma: no cover - operational guardrail
            deps.logger.warning(f"analysis-api mart refresh skipped: {exc}")
        finally:
            if lock_acquired:
                with suppress(Exception):
                    await conn.execute(text("SELECT pg_advisory_unlock(2026051007)"))


async def _latest_post_insight_mart_loop(deps: APIDependencies) -> None:
    if deps.mart_refresh_seconds <= 0:
        return
    await asyncio.sleep(min(deps.mart_refresh_seconds, 30))
    while True:
        await _refresh_latest_post_insight_mart(deps)
        await asyncio.sleep(deps.mart_refresh_seconds)


@asynccontextmanager
async def lifespan(app: FastAPI):
    deps = await init_api_dependencies()
    project_client = build_project_service_client()
    mart_task = asyncio.create_task(_latest_post_insight_mart_loop(deps))
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
