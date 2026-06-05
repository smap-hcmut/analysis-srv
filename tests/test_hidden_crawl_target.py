from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from internal.http.analytics_service import AnalyticsService


@dataclass
class _Result:
    rowcount: int


class _Session:
    def __init__(self, rowcount: int):
        self.rowcount = rowcount
        self.statements: list[str] = []
        self.params: list[dict[str, Any]] = []
        self.committed = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, _exc_type, _exc, _tb):
        return False

    async def execute(self, statement, params):
        self.statements.append(str(statement))
        self.params.append(params)
        return _Result(rowcount=self.rowcount)

    async def commit(self):
        self.committed = True


class _DB:
    def __init__(self, rowcount: int):
        self.session = _Session(rowcount)

    def get_session(self):
        return self.session


@pytest.mark.asyncio
async def test_hide_crawl_target_updates_only_visible_rows():
    db = _DB(rowcount=0)
    service = AnalyticsService(db, project_client=None)  # type: ignore[arg-type]
    refresh_calls = 0

    async def refresh_once() -> bool:
        nonlocal refresh_calls
        refresh_calls += 1
        return True

    service._refresh_latest_mart_once = refresh_once  # type: ignore[method-assign]
    result = await service.hide_crawl_target(
        "80716e8c-a1d8-4eae-9e12-9bff6c4687f5",
        "404751d2-8884-4517-84db-97bc61688e8e",
    )

    assert "INSERT INTO analysis.hidden_crawl_targets" in db.session.statements[0]
    assert "ON CONFLICT (target_id) DO UPDATE" in db.session.statements[0]
    assert "uap_metadata @> CAST(:target_filter AS jsonb)" in db.session.statements[1]
    assert "visibility}', '') <> 'flushed'" in db.session.statements[1]
    assert "deleted_at}', '') = ''" in db.session.statements[1]
    assert db.session.committed is True
    assert result["hidden_rows"] == 0
    assert result["mart_refreshed"] is False
    assert refresh_calls == 0


@pytest.mark.asyncio
async def test_hide_crawl_target_does_not_wait_for_mart_refresh():
    db = _DB(rowcount=3)
    service = AnalyticsService(db, project_client=None)  # type: ignore[arg-type]
    refresh_calls = 0

    async def refresh_once() -> bool:
        nonlocal refresh_calls
        refresh_calls += 1
        return True

    service._refresh_latest_mart_once = refresh_once  # type: ignore[method-assign]
    result = await service.hide_crawl_target(
        "80716e8c-a1d8-4eae-9e12-9bff6c4687f5",
        "404751d2-8884-4517-84db-97bc61688e8e",
    )

    assert result["hidden_rows"] == 3
    assert result["mart_refreshed"] is False
    assert refresh_calls == 0


def test_hidden_target_filter_excludes_control_plane_records():
    service = AnalyticsService(_DB(rowcount=0), project_client=None)  # type: ignore[arg-type]
    expr = service._hidden_target_filter_expr("pi")

    assert "analysis.hidden_crawl_targets" in expr
    assert "hct.target_id::text" in expr
    assert "platform_meta,smap,target_id" in expr
