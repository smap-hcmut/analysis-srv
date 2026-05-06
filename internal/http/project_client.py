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
    applied_crawl_mode: str
    affected_datasource_count: int


class ProjectServiceClient:
    def __init__(self, base_url: str, internal_key: str, timeout_seconds: float = 10.0):
        self.base_url = base_url.rstrip("/")
        self.internal_key = internal_key
        self.timeout_seconds = timeout_seconds
        self._client = httpx.AsyncClient(timeout=self.timeout_seconds)
        self._campaign_cache: dict[str, CachedValue] = {}
        self._project_cache: dict[str, CachedValue] = {}
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

    async def apply_crisis_runtime(
        self,
        project_id: str,
        *,
        status: str,
        reason: str = "",
        event_ref: str = "",
    ) -> CrisisRuntimeApplyResult:
        if not project_id:
            raise BadRequestError("project_id is required")
        if not status:
            raise BadRequestError("status is required")

        normalized_status = str(status).strip().upper()
        if normalized_status not in {"NORMAL", "WARNING", "CRITICAL"}:
            raise BadRequestError(f"invalid crisis status: {status}")

        url = f"{self.base_url}/api/v1/internal/projects/{project_id}/crisis-config/apply-runtime"
        headers = {
            "X-Internal-Key": self.internal_key,
            "Content-Type": "application/json",
        }
        payload = {
            "status": normalized_status,
            "reason": reason,
            "event_ref": event_ref,
        }

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
            applied_crawl_mode=str(data.get("applied_crawl_mode") or ""),
            affected_datasource_count=int(data.get("affected_datasource_count") or 0),
        )

    async def close(self) -> None:
        await self._client.aclose()


def build_project_service_client() -> ProjectServiceClient:
    base_url = os.getenv("ANALYTICS_PROJECT_SERVICE_URL", "http://project-srv.smap.svc.cluster.local")
    internal_key = os.getenv("INTERNAL_KEY") or os.getenv("ANALYTICS_INTERNAL_KEY") or ""
    if not internal_key:
        raise RuntimeError("INTERNAL_KEY or ANALYTICS_INTERNAL_KEY is required")
    return ProjectServiceClient(base_url=base_url, internal_key=internal_key)
