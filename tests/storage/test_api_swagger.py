"""API service tests for Swagger UI."""

import pytest
import httpx
from httpx import ASGITransport

from internal.api.main import app


@pytest.fixture
def anyio_backend():
    return "asyncio"


class TestSwaggerUI:
    """Test Swagger UI accessibility."""

    @pytest.fixture
    async def client(self):
        """Create async test client."""
        transport = ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            yield c

    @pytest.mark.anyio
    async def test_swagger_ui_accessible(self, client):
        """Test /swagger endpoint returns Swagger UI."""
        response = await client.get("/swagger")
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")

    @pytest.mark.anyio
    async def test_swagger_index_html_redirects(self, client):
        """Test /swagger/index.html redirects to /swagger."""
        response = await client.get("/swagger/index.html", follow_redirects=False)
        assert response.status_code == 307

    @pytest.mark.anyio
    async def test_openapi_json_accessible(self, client):
        """Test /openapi.json returns OpenAPI schema."""
        response = await client.get("/openapi.json")
        assert response.status_code == 200
        data = response.json()
        assert "openapi" in data
        assert data["info"]["title"] == "Analytics Engine API"

    @pytest.mark.anyio
    async def test_health_endpoint(self, client):
        """Test health endpoint works."""
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
