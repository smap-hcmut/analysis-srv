"""Integration tests for Posts API endpoints."""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch
from uuid import UUID

from internal.api.main import app


class TestPostsEndpoints:
    """Test suite for Posts API endpoints."""

    @pytest.fixture
    def client(self):
        """FastAPI test client."""
        return TestClient(app)

    @pytest.fixture
    def mock_repository(self):
        """Mock analytics repository."""
        return AsyncMock()

    def test_health_endpoint(self, client):
        """Test basic health endpoint."""
        response = client.get("/health")
        
        assert response.status_code == 200
        assert response.json() == {"status": "healthy"}

    @patch('internal.api.routes.posts.get_db')
    @patch('internal.api.routes.posts.AnalyticsApiRepository')
    def test_get_posts_success(self, mock_repo_class, mock_get_db, client):
        """Test successful posts retrieval."""
        # Mock database session
        mock_db = AsyncMock()
        mock_get_db.return_value.__aenter__.return_value = mock_db
        
        # Mock repository
        mock_repo = AsyncMock()
        mock_repo_class.return_value = mock_repo
        
        # Mock post data
        mock_post = type('MockPost', (), {
            'id': 'test_post_1',
            'platform': 'tiktok', 
            'permalink': 'https://tiktok.com/@user/video/123',
            'content_text': 'Test content for post',
            'author_name': 'Test User',
            'author_username': '@testuser',
            'author_is_verified': True,
            'overall_sentiment': 'POSITIVE',
            'overall_sentiment_score': 0.85,
            'primary_intent': 'DISCUSSION',
            'impact_score': 75.0,
            'risk_level': 'LOW',
            'is_viral': False,
            'is_kol': True,
            'view_count': 10000,
            'like_count': 500,
            'comment_count': 25,
            'published_at': '2025-12-19T10:00:00Z',
            'analyzed_at': '2025-12-19T10:05:00Z',
        })()
        
        mock_repo.get_posts.return_value = ([mock_post], 1)
        
        # Make request
        response = client.get("/api/v1/analytics/posts", params={
            'project_id': '12345678-1234-5678-1234-567812345678',
            'page': 1,
            'page_size': 20
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True
        assert len(data['data']) == 1
        assert data['data'][0]['id'] == 'test_post_1'
        assert data['pagination']['total_items'] == 1

    @patch('internal.api.routes.posts.get_db')
    @patch('internal.api.routes.posts.AnalyticsApiRepository')
    def test_get_posts_with_filters(self, mock_repo_class, mock_get_db, client):
        """Test posts retrieval with filters."""
        # Setup mocks
        mock_db = AsyncMock()
        mock_get_db.return_value.__aenter__.return_value = mock_db
        
        mock_repo = AsyncMock()
        mock_repo_class.return_value = mock_repo
        mock_repo.get_posts.return_value = ([], 0)
        
        # Make request with filters
        response = client.get("/api/v1/analytics/posts", params={
            'project_id': '12345678-1234-5678-1234-567812345678',
            'brand_name': 'Samsung',
            'keyword': 'Galaxy',
            'platform': 'tiktok',
            'sentiment': 'POSITIVE',
            'is_viral': 'true',
            'page': 1,
            'page_size': 10
        })
        
        assert response.status_code == 200
        
        # Verify repository was called with correct filters
        mock_repo.get_posts.assert_called_once()
        call_args = mock_repo.get_posts.call_args
        filters = call_args.kwargs['filters']
        
        assert str(filters.project_id) == '12345678-1234-5678-1234-567812345678'
        assert filters.brand_name == 'Samsung'
        assert filters.keyword == 'Galaxy'
        assert filters.platform == 'tiktok'
        assert filters.sentiment == 'POSITIVE'
        assert filters.is_viral is True

    def test_get_posts_missing_project_id(self, client):
        """Test posts request without required project_id."""
        response = client.get("/api/v1/analytics/posts")
        
        assert response.status_code == 422  # Validation error

    @patch('internal.api.routes.posts.get_db') 
    @patch('internal.api.routes.posts.AnalyticsApiRepository')
    def test_get_post_by_id_found(self, mock_repo_class, mock_get_db, client):
        """Test retrieving specific post by ID."""
        # Setup mocks
        mock_db = AsyncMock()
        mock_get_db.return_value.__aenter__.return_value = mock_db
        
        mock_repo = AsyncMock()
        mock_repo_class.return_value = mock_repo
        
        # Mock detailed post data
        mock_post = type('MockPost', (), {
            'id': 'test_post_detail',
            'platform': 'tiktok',
            'permalink': 'https://tiktok.com/@user/video/456',
            'content_text': 'Detailed test content',
            'content_transcription': None,
            'hashtags': ['#test', '#api'],
            'media_duration': 30,
            'author_id': 'user123',
            'author_name': 'Detailed User',
            'author_username': '@detaileduser',
            'author_avatar_url': 'https://avatar.url',
            'author_is_verified': False,
            'follower_count': 5000,
            'overall_sentiment': 'NEUTRAL',
            'overall_sentiment_score': 0.1,
            'overall_confidence': 0.9,
            'sentiment_probabilities': {'POSITIVE': 0.3, 'NEUTRAL': 0.5, 'NEGATIVE': 0.2},
            'primary_intent': 'DISCUSSION',
            'intent_confidence': 0.85,
            'impact_score': 45.0,
            'risk_level': 'MEDIUM',
            'is_viral': False,
            'is_kol': False,
            'impact_breakdown': {'engagement_score': 25.0, 'reach_score': 3.5},
            'aspects_breakdown': None,
            'keywords': None,
            'view_count': 5000,
            'like_count': 100,
            'comment_count': 10,
            'share_count': 20,
            'save_count': 15,
            'published_at': '2025-12-19T12:00:00Z',
            'analyzed_at': '2025-12-19T12:05:00Z',
            'crawled_at': '2025-12-19T12:02:00Z',
            'brand_name': 'TestBrand',
            'keyword': 'test',
            'job_id': 'job_123',
            'comments': []
        })()
        
        mock_repo.get_post_by_id.return_value = mock_post
        
        # Make request
        response = client.get("/api/v1/analytics/posts/test_post_detail")
        
        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True
        assert data['data']['id'] == 'test_post_detail'
        assert data['data']['author_name'] == 'Detailed User'
        assert data['data']['comments_total'] == 0

    @patch('internal.api.routes.posts.get_db')
    @patch('internal.api.routes.posts.AnalyticsApiRepository')
    def test_get_post_by_id_not_found(self, mock_repo_class, mock_get_db, client):
        """Test retrieving non-existent post by ID."""
        # Setup mocks
        mock_db = AsyncMock()
        mock_get_db.return_value.__aenter__.return_value = mock_db
        
        mock_repo = AsyncMock()
        mock_repo_class.return_value = mock_repo
        mock_repo.get_post_by_id.return_value = None
        
        # Make request
        response = client.get("/api/v1/analytics/posts/nonexistent_post")
        
        assert response.status_code == 404