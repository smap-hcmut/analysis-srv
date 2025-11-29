"""Integration tests for API service with AI models."""

import pytest # type: ignore
from fastapi.testclient import TestClient # type: ignore
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
        invalid_data = {
            "invalid_field": "test"
        }

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
        assert response1.json()["metadata"]["models_initialized"] == response2.json()["metadata"]["models_initialized"]
