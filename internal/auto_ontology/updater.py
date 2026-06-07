"""AutoOntologyUpdater — discover and publish ontology keywords automatically.

Scheduled inside analysis-consumer. For each project whose domain config
resolves to the ``_default`` fallback (i.e. no canonical ontology shipped
yet), we:

  1. Pull the last ``window_hours`` post_insight rows for that project.
  2. Concatenate the cleaned content.
  3. Ask SpacyYake to surface the top-K keyphrases.
  4. Filter out anything already in the existing ontology rules (Redis).
  5. Write a single keyword group ``auto-discovered`` to the project's
     Redis ontology key so analysis-consumer + project-srv readers see it
     on the next refresh.

Each rule is tagged ``auto_generated: true`` so operators (and the
``feedback`` migration that captures human edits) can prune false
positives without touching the canonical YAML registry.
"""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field
from typing import Any, Iterable, Optional

from sqlalchemy import text


_REDIS_KEY_TEMPLATE = "smap:project:ontology-rules:{project_id}"
_AUTO_GROUP_NAME = "auto-discovered"


@dataclass
class AutoOntologyConfig:
    """Tunable knobs for the discovery loop. All from env in production."""

    enabled: bool = True
    period_seconds: int = 1800        # 30 min between sweeps
    window_hours: int = 6              # look at the last 6h of post_insight
    min_rows_per_project: int = 50     # need this much signal before suggesting
    top_keywords: int = 12             # cap suggestions per project
    min_keyword_score: float = 0.05    # SpacyYake / YAKE keyword score floor
    discover_only_default_domain: bool = True  # skip projects with canonical
    discover_only_active: bool = True            # require project.status=ACTIVE


@dataclass
class _ProjectCandidate:
    project_id: str
    project_name: str
    domain_code: str
    row_count: int


@dataclass
class _Discovered:
    project_id: str
    keywords: list[str]
    sample_size: int
    extracted_at: float = field(default_factory=time.time)


class AutoOntologyUpdater:
    """Owns the auto-discovery loop. Wired by the consumer registry."""

    def __init__(
        self,
        deps,
        keyword_extractor,
        redis_client,
        cfg: Optional[AutoOntologyConfig] = None,
    ) -> None:
        self._deps = deps
        self._logger = deps.logger
        self._yake = keyword_extractor
        self._redis = redis_client
        self._cfg = cfg or AutoOntologyConfig()
        self._task: Optional[asyncio.Task] = None
        self._stop = False

    def start(self) -> None:
        if not self._cfg.enabled:
            self._logger.info("auto_ontology: disabled by config")
            return
        if self._task is not None and not self._task.done():
            return
        self._stop = False
        self._task = asyncio.create_task(self._run(), name="auto-ontology")
        self._logger.info(
            "auto_ontology: started, period=%ds window=%dh",
            self._cfg.period_seconds,
            self._cfg.window_hours,
        )

    async def stop(self) -> None:
        self._stop = True
        if self._task is not None and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass
            self._task = None

    async def _run(self) -> None:
        # Stagger the first sweep so we do not pile onto pod startup.
        await asyncio.sleep(min(60, self._cfg.period_seconds // 2))
        while not self._stop:
            try:
                await self.run_once()
            except Exception as exc:
                self._logger.error("auto_ontology: sweep failed: %s", exc)
            try:
                await asyncio.sleep(self._cfg.period_seconds)
            except asyncio.CancelledError:
                break

    async def run_once(self) -> int:
        """Single sweep — returns number of projects touched."""
        candidates = await self._fetch_candidates()
        if not candidates:
            return 0

        touched = 0
        for cand in candidates:
            try:
                keywords = await self._discover_for(cand)
                if not keywords:
                    continue
                wrote = await self._publish(cand, keywords)
                if wrote:
                    touched += 1
                    self._logger.info(
                        "auto_ontology: project=%s domain=%s suggested %d keywords",
                        cand.project_id, cand.domain_code, len(keywords),
                    )
            except Exception as exc:
                self._logger.warning(
                    "auto_ontology: project=%s failed: %s",
                    cand.project_id, exc,
                )
        return touched

    async def _fetch_candidates(self) -> list[_ProjectCandidate]:
        """Pick projects worth scanning this round."""
        if not self._deps.db.engine:
            return []
        filters = ["pi.created_at >= NOW() - (:hours * INTERVAL '1 hour')"]
        params: dict[str, Any] = {"hours": self._cfg.window_hours}
        if self._cfg.discover_only_default_domain:
            filters.append(
                "(pi.uap_metadata #>> '{domain_type_code}' IS NULL "
                "OR pi.uap_metadata #>> '{domain_type_code}' IN ('', '_default'))"
            )
        where = " AND ".join(filters)
        sql = text(
            f"""
            SELECT pi.project_id AS project_id,
                   COALESCE(MAX(pi.uap_metadata #>> '{{domain_type_code}}'), '_default') AS domain_code,
                   count(*) AS row_count
            FROM analysis.post_insight pi
            WHERE {where}
            GROUP BY pi.project_id
            HAVING count(*) >= :min_rows
            ORDER BY row_count DESC
            LIMIT 32
            """
        )
        async with self._deps.db.engine.connect() as conn:
            conn = await conn.execution_options(isolation_level="AUTOCOMMIT")
            result = await conn.execute(
                sql,
                {**params, "min_rows": self._cfg.min_rows_per_project},
            )
            rows = [dict(r._mapping) for r in result.fetchall()]
        return [
            _ProjectCandidate(
                project_id=str(r["project_id"]),
                project_name=str(r["project_id"]),
                domain_code=str(r.get("domain_code") or "_default"),
                row_count=int(r["row_count"]),
            )
            for r in rows
        ]

    async def _discover_for(self, cand: _ProjectCandidate) -> list[str]:
        async with self._deps.db.engine.connect() as conn:
            conn = await conn.execution_options(isolation_level="AUTOCOMMIT")
            result = await conn.execute(
                text(
                    """
                    SELECT content
                    FROM analysis.post_insight
                    WHERE project_id = :pid
                      AND created_at >= NOW() - (:hours * INTERVAL '1 hour')
                      AND COALESCE(content, '') <> ''
                    ORDER BY created_at DESC
                    LIMIT 400
                    """
                ),
                {"pid": cand.project_id, "hours": self._cfg.window_hours},
            )
            samples = [str(r._mapping["content"]) for r in result.fetchall()]
        if not samples:
            return []

        joined = " \n ".join(samples)
        try:
            extracted = await asyncio.get_running_loop().run_in_executor(
                None, self._yake.extract, joined
            )
        except Exception as exc:
            self._logger.warning(
                "auto_ontology: yake extract failed project=%s: %s",
                cand.project_id, exc,
            )
            return []

        ranked = []
        for kw in getattr(extracted, "yake_keywords", []) or []:
            phrase = str(getattr(kw, "phrase", "") or "").strip()
            score = float(getattr(kw, "score", 0.0) or 0.0)
            if not phrase or score < self._cfg.min_keyword_score:
                continue
            if len(phrase.split()) > 5:
                continue
            ranked.append((phrase, score))
        ranked.sort(key=lambda p: p[1], reverse=True)
        return [phrase for phrase, _ in ranked[: self._cfg.top_keywords]]

    async def _publish(self, cand: _ProjectCandidate, keywords: list[str]) -> bool:
        """Merge discovered keywords into the project's ontology Redis key.

        Returns True when the cache was actually updated (false positives
        already present in the canonical rules are skipped silently).
        """
        if not self._redis:
            return False
        key = _REDIS_KEY_TEMPLATE.format(project_id=cand.project_id)
        existing_raw = await self._safe_redis_get(key)
        try:
            existing = json.loads(existing_raw) if existing_raw else {}
        except Exception:
            existing = {}
        rules = list(existing.get("rules") or [])
        already_known = self._existing_phrases(rules)

        fresh = [w for w in keywords if w.lower() not in already_known]
        if not fresh:
            return False

        auto_rule = {
            "name": _AUTO_GROUP_NAME,
            "auto_generated": True,
            "keywords": fresh,
            "weight": 10,
            "updated_at": int(time.time()),
            "sample_size": cand.row_count,
        }
        # Replace any prior auto-discovered rule so the cache stays bounded
        # to one merged batch per project; existing manual rules survive.
        rules = [r for r in rules if r.get("name") != _AUTO_GROUP_NAME]
        rules.append(auto_rule)

        payload = {
            **existing,
            "project_id": cand.project_id,
            "enabled": existing.get("enabled", True),
            "rules": rules,
            "updated_at": time.time(),
            "updated_by": "auto-ontology",
        }
        await self._safe_redis_set(key, json.dumps(payload, ensure_ascii=False))
        return True

    async def _safe_redis_get(self, key: str) -> str:
        try:
            return await self._redis.get(key)
        except Exception:
            return ""

    async def _safe_redis_set(self, key: str, value: str) -> None:
        try:
            await self._redis.set(key, value)
        except Exception as exc:
            self._logger.warning("auto_ontology: redis set failed key=%s err=%s", key, exc)

    @staticmethod
    def _existing_phrases(rules: Iterable[dict[str, Any]]) -> set[str]:
        out: set[str] = set()
        for rule in rules:
            for kw in rule.get("keywords", []) or []:
                if isinstance(kw, str):
                    out.add(kw.strip().lower())
        return out


__all__ = ["AutoOntologyUpdater", "AutoOntologyConfig"]
