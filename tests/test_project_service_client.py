import pytest

from internal.http.errors import BadRequestError, UpstreamError
from internal.http.project_client import ProjectServiceClient


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict):
        self.status_code = status_code
        self._payload = payload
        self.text = str(payload)
        self.content = b"{}"

    def json(self):
        return self._payload


class _FakeAsyncClient:
    def __init__(self, response: _FakeResponse):
        self.response = response
        self.last_url = ""
        self.last_headers = {}
        self.last_json = {}

    async def post(self, url, headers=None, json=None):
        self.last_url = url
        self.last_headers = headers or {}
        self.last_json = json or {}
        return self.response

    async def aclose(self):
        return None


@pytest.mark.asyncio
async def test_apply_crisis_runtime_rejects_invalid_status():
    client = ProjectServiceClient(
        base_url="http://project-srv.local",
        internal_key="k",
    )

    with pytest.raises(BadRequestError):
        await client.apply_crisis_runtime(
            "proj-1",
            status="watch",
        )

    await client.close()


@pytest.mark.asyncio
async def test_apply_crisis_runtime_success():
    client = ProjectServiceClient(
        base_url="http://project-srv.local",
        internal_key="secret",
    )
    fake = _FakeAsyncClient(
        _FakeResponse(
            200,
            {
                "data": {
                    "project_id": "proj-123",
                    "crisis_status": "CRITICAL",
                    "applied_crawl_mode": "CRISIS",
                    "affected_datasource_count": 4,
                }
            },
        )
    )
    client._client = fake

    out = await client.apply_crisis_runtime(
        "proj-123",
        status="critical",
        reason="auto",
        event_ref="analysis-run:x",
    )

    assert out.project_id == "proj-123"
    assert out.crisis_status == "CRITICAL"
    assert out.applied_crawl_mode == "CRISIS"
    assert out.affected_datasource_count == 4
    assert fake.last_url.endswith(
        "/api/v1/internal/projects/proj-123/crisis-config/apply-runtime"
    )
    assert fake.last_headers.get("X-Internal-Key") == "secret"
    assert fake.last_json.get("status") == "CRITICAL"


@pytest.mark.asyncio
async def test_apply_crisis_runtime_raises_upstream_error_on_http_failure():
    client = ProjectServiceClient(
        base_url="http://project-srv.local",
        internal_key="secret",
    )
    client._client = _FakeAsyncClient(_FakeResponse(500, {"error": "boom"}))

    with pytest.raises(UpstreamError):
        await client.apply_crisis_runtime("proj-err", status="WARNING")
