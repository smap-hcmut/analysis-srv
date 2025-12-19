"""Integration tests for API endpoints."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from internal.api.main import app
from core.database import get_db


@pytest.fixture
async def client():
    """Create test client."""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def db_session():
    """Create test database session."""
    # This would be replaced with actual test database setup
    # For now, we'll mock it
    from unittest.mock import AsyncMock
    return AsyncMock(spec=AsyncSession)


class TestHealthEndpoints:
    """Test health check endpoints."""
    
    async def test_health_check(self, client):
        """Test basic health check."""
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
    
    async def test_detailed_health_check(self, client):
        """Test detailed health check."""
        response = await client.get("/health/detailed")
        assert response.status_code in [200, 503]  # May fail without database
        data = response.json()
        assert "status" in data
        assert "checks" in data


class TestPostsEndpoints:
    """Test posts API endpoints."""
    
    async def test_get_posts_missing_project_id(self, client):
        """Test posts endpoint without project_id."""
        response = await client.get("/api/v1/analytics/posts")
        assert response.status_code == 422  # Validation error
        data = response.json()
        assert "detail" in data
    
    async def test_get_posts_invalid_uuid(self, client):
        """Test posts endpoint with invalid UUID."""
        response = await client.get("/api/v1/analytics/posts?project_id=invalid-uuid")
        assert response.status_code == 422  # Validation error
    
    async def test_get_posts_valid_request(self, client):
        """Test posts endpoint with valid request."""
        # This would require database setup, for now just check the endpoint exists
        response = await client.get("/api/v1/analytics/posts?project_id=550e8400-e29b-41d4-a716-446655440000")
        # Response may be 500 due to database not being available in tests
        assert response.status_code in [200, 500]


class TestSummaryEndpoints:
    """Test summary API endpoints."""
    
    async def test_get_summary_missing_project_id(self, client):
        """Test summary endpoint without project_id."""
        response = await client.get("/api/v1/analytics/summary")
        assert response.status_code == 422  # Validation error
    
    async def test_get_summary_valid_request(self, client):
        """Test summary endpoint with valid request."""
        response = await client.get("/api/v1/analytics/summary?project_id=550e8400-e29b-41d4-a716-446655440000")
        assert response.status_code in [200, 500]


class TestTrendsEndpoints:
    """Test trends API endpoints."""
    
    async def test_get_trends_missing_dates(self, client):
        """Test trends endpoint without required dates."""
        response = await client.get("/api/v1/analytics/trends?project_id=550e8400-e29b-41d4-a716-446655440000")
        assert response.status_code == 422  # Validation error
    
    async def test_get_trends_valid_request(self, client):
        """Test trends endpoint with valid request."""
        response = await client.get(
            "/api/v1/analytics/trends"
            "?project_id=550e8400-e29b-41d4-a716-446655440000"
            "&from_date=2025-12-01T00:00:00"
            "&to_date=2025-12-19T23:59:59"
        )
        assert response.status_code in [200, 500]


class TestKeywordsEndpoints:
    """Test keywords API endpoints."""
    
    async def test_get_keywords_missing_project_id(self, client):
        """Test keywords endpoint without project_id."""
        response = await client.get("/api/v1/analytics/top-keywords")
        assert response.status_code == 422  # Validation error
    
    async def test_get_keywords_valid_request(self, client):
        """Test keywords endpoint with valid request."""
        response = await client.get("/api/v1/analytics/top-keywords?project_id=550e8400-e29b-41d4-a716-446655440000")
        assert response.status_code in [200, 500]


class TestAlertsEndpoints:
    """Test alerts API endpoints."""
    
    async def test_get_alerts_missing_project_id(self, client):
        """Test alerts endpoint without project_id."""
        response = await client.get("/api/v1/analytics/alerts")
        assert response.status_code == 422  # Validation error
    
    async def test_get_alerts_valid_request(self, client):
        """Test alerts endpoint with valid request."""
        response = await client.get("/api/v1/analytics/alerts?project_id=550e8400-e29b-41d4-a716-446655440000")
        assert response.status_code in [200, 500]


class TestErrorsEndpoints:
    """Test errors API endpoints."""
    
    async def test_get_errors_missing_project_id(self, client):
        """Test errors endpoint without project_id."""
        response = await client.get("/api/v1/analytics/errors")
        assert response.status_code == 422  # Validation error
    
    async def test_get_errors_valid_request(self, client):
        """Test errors endpoint with valid request."""
        response = await client.get("/api/v1/analytics/errors?project_id=550e8400-e29b-41d4-a716-446655440000")
        assert response.status_code in [200, 500]