from __future__ import annotations

import os
import time
from asyncio import gather
from dataclasses import dataclass

import httpx

from internal.http.errors import BadRequestError, UpstreamError


@dataclass
class CampaignProjects:
    id: str
    name: str
    project_ids: list[str]
    projects: list[dict[str, str]]


@dataclass
class CachedValue:
    value: object
    expires_at: float


@dataclass
class CrisisRuntimeApplyResult:
    project_id: str
    crisis_status: str
    crisis_level: str
    applied_crawl_mode: str
    affected_datasource_count: int
    noop_reason: str = ""


@dataclass
class ProjectCrisisRuntimeConfig:
    project_id: str
    project_name: str
    campaign_id: str
    owner_user_id: str
    crisis_config: dict


class ProjectServiceClient:
    def __init__(self, base_url: str, internal_key: str, timeout_seconds: float = 10.0):
        self.base_url = base_url.rstrip("/")
        self.internal_key = internal_key
        self.timeout_seconds = timeout_seconds
        self._client = httpx.AsyncClient(timeout=self.timeout_seconds)
        self._campaign_cache: dict[str, CachedValue] = {}
        self._project_cache: dict[str, CachedValue] = {}
        self._crisis_config_cache: dict[str, CachedValue] = {}
        self._ttl_seconds = 300.0

    async def get_campaign_projects(self, campaign_id: str) -> CampaignProjects:
        if not campaign_id:
            raise BadRequestError("campaignId is required")

        cached = self._campaign_cache.get(campaign_id)
        if cached and cached.expires_at > time.time():
            return cached.value  # type: ignore[return-value]

        url = f"{self.base_url}/api/v1/internal/campaigns/{campaign_id}"
        headers = {"X-Internal-Key": self.internal_key}

        try:
            response = await self._client.get(url, headers=headers)
        except httpx.HTTPError as exc:
            raise UpstreamError(f"project service unavailable: {exc}") from exc

        if response.status_code == 404:
            return CampaignProjects(id=campaign_id, name="Campaign", project_ids=[], projects=[])

        if response.status_code >= 400:
            raise UpstreamError(
                f"project service failed ({response.status_code}): {response.text}"
            )

        payload = response.json()
        result = CampaignProjects(
            id=str(payload.get("id") or campaign_id),
            name=str(payload.get("name") or "Campaign"),
            project_ids=[str(item) for item in payload.get("project_ids") or []],
            projects=[
                {
                    "id": str(item.get("id") or ""),
                    "name": str(item.get("name") or item.get("id") or ""),
                }
                for item in payload.get("projects") or []
                if isinstance(item, dict)
            ],
        )
        self._campaign_cache[campaign_id] = CachedValue(
            value=result,
            expires_at=time.time() + self._ttl_seconds,
        )
        return result

    async def get_project_names(self, project_ids: list[str]) -> dict[str, str]:
        names: dict[str, str] = {}
        missing: list[str] = []
        now = time.time()
        for project_id in project_ids:
            cached = self._project_cache.get(project_id)
            if cached and cached.expires_at > now:
                names[project_id] = str(cached.value)
            else:
                missing.append(project_id)

        if missing:
            fetched = await gather(*(self._get_project_name(project_id) for project_id in missing))
            for project_id, name in zip(missing, fetched, strict=True):
                names[project_id] = name
                self._project_cache[project_id] = CachedValue(
                    value=name,
                    expires_at=time.time() + self._ttl_seconds,
                )

        return names

    def project_name_map(self, campaign: CampaignProjects) -> dict[str, str]:
        names = {project["id"]: project["name"] for project in campaign.projects if project.get("id")}
        for project_id in campaign.project_ids:
            names.setdefault(project_id, project_id)
        return names

    async def _get_project_name(self, project_id: str) -> str:
        url = f"{self.base_url}/api/v1/internal/projects/{project_id}"
        headers = {"X-Internal-Key": self.internal_key}

        try:
            response = await self._client.get(url, headers=headers)
        except httpx.HTTPError as exc:
            raise UpstreamError(f"project detail unavailable: {exc}") from exc

        if response.status_code == 404:
            return project_id

        if response.status_code >= 400:
            raise UpstreamError(
                f"project detail failed ({response.status_code}): {response.text}"
            )

        payload = response.json()
        data = payload.get("data") if isinstance(payload, dict) else None
        project = data.get("project") if isinstance(data, dict) else None
        if isinstance(project, dict) and project.get("name"):
            return str(project["name"])
        return project_id

    async def get_crisis_runtime_config(self, project_id: str) -> ProjectCrisisRuntimeConfig:
        if not project_id:
            raise BadRequestError("project_id is required")

        cached = self._crisis_config_cache.get(project_id)
        if cached and cached.expires_at > time.time():
            return cached.value  # type: ignore[return-value]

        url = f"{self.base_url}/api/v1/internal/projects/{project_id}/crisis-config"
        headers = {"X-Internal-Key": self.internal_key}

        try:
            response = await self._client.get(url, headers=headers)
        except httpx.HTTPError as exc:
            raise UpstreamError(f"project crisis config unavailable: {exc}") from exc

        if response.status_code >= 400:
            raise UpstreamError(
                f"project crisis config failed ({response.status_code}): {response.text}"
            )

        payload = response.json()
        data = payload.get("data") if isinstance(payload, dict) else {}
        if not isinstance(data, dict):
            data = {}

        result = ProjectCrisisRuntimeConfig(
            project_id=str(data.get("project_id") or project_id),
            project_name=str(data.get("project_name") or project_id),
            campaign_id=str(data.get("campaign_id") or ""),
            owner_user_id=str(data.get("owner_user_id") or ""),
            crisis_config=data.get("crisis_config") if isinstance(data.get("crisis_config"), dict) else {},
        )
        self._crisis_config_cache[project_id] = CachedValue(
            value=result,
            expires_at=time.time() + 60.0,
        )
        return result

    async def apply_crisis_runtime(
        self,
        project_id: str,
        *,
        status: str | None = None,
        crisis_level: str | None = None,
        reason: str = "",
        event_ref: str = "",
    ) -> CrisisRuntimeApplyResult:
        if not project_id:
            raise BadRequestError("project_id is required")
        if not status and not crisis_level:
            raise BadRequestError("status or crisis_level is required")

        normalized_status = str(status or "").strip().upper()
        normalized_level = str(crisis_level or status or "").strip().upper()
        if normalized_status and normalized_status not in {"NORMAL", "WATCH", "WARNING", "CRITICAL"}:
            raise BadRequestError(f"invalid crisis status: {status}")
        if normalized_level not in {"NONE", "NORMAL", "WATCH", "WARNING", "CRITICAL"}:
            raise BadRequestError(f"invalid crisis level: {crisis_level}")

        url = f"{self.base_url}/api/v1/internal/projects/{project_id}/crisis-config/apply-runtime"
        headers = {
            "X-Internal-Key": self.internal_key,
            "Content-Type": "application/json",
        }
        payload = {
            "crisis_level": normalized_level,
            "reason": reason,
            "event_ref": event_ref,
        }
        if normalized_status:
            payload["status"] = normalized_status

        try:
            response = await self._client.post(url, headers=headers, json=payload)
        except httpx.HTTPError as exc:
            raise UpstreamError(f"project runtime apply unavailable: {exc}") from exc

        if response.status_code >= 400:
            raise UpstreamError(
                f"project runtime apply failed ({response.status_code}): {response.text}"
            )

        payload_data = response.json() if response.content else {}
        data = payload_data.get("data") if isinstance(payload_data, dict) else {}
        return CrisisRuntimeApplyResult(
            project_id=str(data.get("project_id") or project_id),
            crisis_status=str(data.get("crisis_status") or normalized_status),
            crisis_level=str(data.get("crisis_level") or normalized_level),
            applied_crawl_mode=str(data.get("applied_crawl_mode") or ""),
            affected_datasource_count=int(data.get("affected_datasource_count") or 0),
            noop_reason=str(data.get("noop_reason") or ""),
        )

    async def close(self) -> None:
        await self._client.aclose()


def build_project_service_client() -> ProjectServiceClient:
    base_url = os.getenv("ANALYTICS_PROJECT_SERVICE_URL", "http://project-srv.smap.svc.cluster.local")
    internal_key = os.getenv("INTERNAL_KEY") or os.getenv("ANALYTICS_INTERNAL_KEY") or ""
    if not internal_key:
        raise RuntimeError("INTERNAL_KEY or ANALYTICS_INTERNAL_KEY is required")
    return ProjectServiceClient(base_url=base_url, internal_key=internal_key)
