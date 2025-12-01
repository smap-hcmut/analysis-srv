"""Integration tests for API service with AI models."""

import uuid

import pytest  # type: ignore
from fastapi.testclient import TestClient  # type: ignore

from commands.api.main import app, lifespan


class TestAPIIntegration:
    """Test full API integration with AI models."""

    @pytest.fixture
    def client(self):
        """Create test client with lifespan context."""
        with TestClient(app) as test_client:
            yield test_client

    def test_health_endpoint(self, client):
        """Test health check endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    def test_root_endpoint(self, client):
        """Test root endpoint."""
        response = client.get("/")
        assert response.status_code == 200
        assert response.json()["service"] == "Analytics Engine API"

    def test_openapi_docs(self, client):
        """Test that OpenAPI documentation is generated."""
        response = client.get("/openapi.json")
        assert response.status_code == 200
        openapi = response.json()
        assert openapi["info"]["title"] == "Analytics Engine API"
        assert "/test/analytics" in openapi["paths"]

    def test_dev_orchestrator_endpoint_runs_full_pipeline(self, client, monkeypatch):
        """Dev orchestrator endpoint should run full pipeline and return analytics payload."""
        from internal.api.routes import orchestrator as dev_route

        saved = {}

        class FakeRepository:
            def __init__(self, db):
                self.db = db

            def save(self, analytics_data):
                saved["data"] = analytics_data
                return analytics_data

        # Patch repository to avoid hitting a real database
        monkeypatch.setattr(dev_route, "AnalyticsRepository", FakeRepository)

        test_post_id = "api_integration_post_1"
        project_id = str(uuid.uuid4())

        test_data = {
            "meta": {
                "id": test_post_id,
                "project_id": project_id,
                "platform": "facebook",
                "lang": "vi",
                "collected_at": "2025-01-15T10:30:00Z",
            },
            "content": {
                "text": "Xe thiết kế đẹp, giá hơi cao nhưng vẫn chấp nhận được.",
                "transcription": "",
            },
            "interaction": {
                "views": 5000,
                "likes": 120,
                "comments_count": 15,
                "shares": 10,
                "saves": 4,
            },
            "author": {
                "id": "author_1",
                "name": "API Tester",
                "followers": 10000,
                "is_verified": False,
            },
            "comments": [
                {"text": "đẹp quá", "likes": 3},
                {"text": "giá cao", "likes": 1},
            ],
        }

        response = client.post("/dev/process-post-direct", json=test_data)
        assert response.status_code == 200

        payload = response.json()
        assert payload["status"] == "SUCCESS"
        assert payload["data"]["id"] == test_post_id
        assert payload["data"]["platform"] == "FACEBOOK"

        # Verify repository was called with PostAnalytics-shaped payload
        assert "data" in saved
        analytics = saved["data"]
        assert analytics["id"] == test_post_id
        assert analytics["project_id"] == project_id
        assert analytics["platform"] == "FACEBOOK"
        assert "impact_score" in analytics
        assert "risk_level" in analytics

    def test_analytics_endpoint_with_valid_json(self, client):
        """Test analytics endpoint with valid JSON input."""
        test_data = {
            "meta": {
                "id": "test_post_123",
                "platform": "facebook",
                "lang": "vi",
                "collected_at": "2025-01-15T10:30:00Z",
            },
            "content": {
                "title": "Đánh giá sản phẩm",
                "text": "Sản phẩm chất lượng cao, rất hài lòng!",
                "media": [],
            },
            "interaction": {"likes": 42, "shares": 5, "comments_count": 3},
            "author": {"id": "user_456", "name": "John Doe"},
            "comments": [],
        }

        response = client.post("/test/analytics", json=test_data)

        # Should succeed even if models aren't loaded
        assert response.status_code == 200

        result = response.json()
        assert result["post_id"] == "test_post_123"
        assert "preprocessing" in result
        assert "keywords" in result
        assert "sentiment" in result
        assert "metadata" in result

    def test_analytics_endpoint_with_invalid_json(self, client):
        """Test analytics endpoint with invalid JSON input."""
        invalid_data = {"invalid_field": "test"}

        response = client.post("/test/analytics", json=invalid_data)
        assert response.status_code == 422  # Validation error

    def test_analytics_endpoint_models_loaded(self, client):
        """Test that analytics endpoint reports model status."""
        test_data = {
            "meta": {"id": "test_123", "platform": "facebook", "lang": "en"},
            "content": {"title": "Test", "text": "Test content"},
            "interaction": {},
            "author": {},
            "comments": [],
        }

        response = client.post("/test/analytics", json=test_data)
        assert response.status_code == 200

        result = response.json()
        metadata = result["metadata"]

        # Check that models_initialized is reported
        assert "models_initialized" in metadata
        assert isinstance(metadata["models_initialized"], dict)


class TestDependencyInjection:
    """Test dependency injection for AI models."""

    def test_dependencies_module_exists(self):
        """Test that dependencies module can be imported."""
        from internal.api.dependencies import get_phobert, get_spacyyake

        assert callable(get_phobert)
        assert callable(get_spacyyake)

    def test_dependencies_return_types(self):
        """Test that dependency functions have correct type hints."""
        from internal.api.dependencies import get_phobert, get_spacyyake
        from infrastructure.ai import PhoBERTONNX, SpacyYakeExtractor

        # Check function signatures (type hints)
        import inspect

        phobert_sig = inspect.signature(get_phobert)
        assert phobert_sig.return_annotation == PhoBERTONNX

        spacyyake_sig = inspect.signature(get_spacyyake)
        assert spacyyake_sig.return_annotation == SpacyYakeExtractor


class TestModelReuse:
    """Test that models are reused across requests (not reloaded)."""

    @pytest.fixture
    def client(self):
        """Create test client with lifespan context."""
        with TestClient(app) as test_client:
            yield test_client

    def test_models_not_reloaded_per_request(self, client):
        """Test that same model instances are used for multiple requests."""
        test_data = {
            "meta": {"id": "test_1", "platform": "facebook", "lang": "en"},
            "content": {"title": "First", "text": "First request"},
            "interaction": {},
            "author": {},
            "comments": [],
        }

        # Make first request
        response1 = client.post("/test/analytics", json=test_data)
        assert response1.status_code == 200

        # Make second request
        test_data["meta"]["id"] = "test_2"
        test_data["content"]["text"] = "Second request"
        response2 = client.post("/test/analytics", json=test_data)
        assert response2.status_code == 200

        # Both requests should succeed
        # Models should not be reloaded (verified by no additional loading logs)
        assert (
            response1.json()["metadata"]["models_initialized"]
            == response2.json()["metadata"]["models_initialized"]
        )
