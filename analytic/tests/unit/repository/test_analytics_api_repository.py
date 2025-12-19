"""Unit tests for AnalyticsApiRepository."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID
from datetime import datetime

from interfaces.analytics_api_repository import PostFilters, ErrorFilters
from models.schemas.base import PaginationParams
from repository.analytics_api_repository import AnalyticsApiRepository


class TestAnalyticsApiRepository:
    """Test suite for AnalyticsApiRepository."""

    @pytest.fixture
    def mock_db_session(self):
        """Mock async database session."""
        session = AsyncMock()
        return session

    @pytest.fixture
    def repository(self, mock_db_session):
        """Create repository instance with mocked session."""
        return AnalyticsApiRepository(mock_db_session)

    @pytest.fixture
    def sample_filters(self):
        """Sample post filters for testing."""
        return PostFilters(
            project_id=UUID('12345678-1234-5678-1234-567812345678'),
            brand_name='TestBrand',
            keyword='test_keyword'
        )

    @pytest.fixture
    def sample_pagination(self):
        """Sample pagination parameters."""
        return PaginationParams(page=1, page_size=20)

    @pytest.mark.asyncio
    async def test_health_check_success(self, repository, mock_db_session):
        """Test successful health check."""
        # Mock successful query
        mock_result = AsyncMock()
        mock_result.scalar.return_value = 1
        mock_db_session.execute.return_value = mock_result
        
        result = await repository.health_check()
        
        assert result is True
        mock_db_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_health_check_failure(self, repository, mock_db_session):
        """Test health check failure."""
        # Mock database exception
        mock_db_session.execute.side_effect = Exception("Database connection failed")
        
        result = await repository.health_check()
        
        assert result is False

    @pytest.mark.asyncio
    async def test_get_posts_basic(self, repository, mock_db_session, sample_filters, sample_pagination):
        """Test basic posts retrieval."""
        # Mock query results
        mock_posts = [MagicMock() for _ in range(5)]
        mock_count_result = AsyncMock()
        mock_count_result.scalar.return_value = 100
        
        mock_posts_result = AsyncMock()
        mock_posts_result.scalars.return_value.all.return_value = mock_posts
        
        # Setup mock execute calls (count first, then posts)
        mock_db_session.execute.side_effect = [mock_count_result, mock_posts_result]
        
        posts, total_count = await repository.get_posts(
            filters=sample_filters,
            pagination=sample_pagination,
            sort_by="analyzed_at",
            sort_order="desc"
        )
        
        assert len(posts) == 5
        assert total_count == 100
        assert mock_db_session.execute.call_count == 2

    @pytest.mark.asyncio
    async def test_get_summary_stats(self, repository, mock_db_session):
        """Test summary statistics retrieval."""
        project_id = UUID('12345678-1234-5678-1234-567812345678')
        
        # Mock all query results
        mock_results = [
            # total_posts
            AsyncMock(scalar=MagicMock(return_value=150)),
            # total_comments
            AsyncMock(scalar=MagicMock(return_value=2500)),
            # sentiment_distribution
            AsyncMock(fetchall=MagicMock(return_value=[('POSITIVE', 80), ('NEGATIVE', 30), ('NEUTRAL', 40)])),
            # risk_distribution
            AsyncMock(fetchall=MagicMock(return_value=[('LOW', 100), ('MEDIUM', 30), ('HIGH', 20)])),
            # intent_distribution  
            AsyncMock(fetchall=MagicMock(return_value=[('DISCUSSION', 90), ('COMPLAINT', 40), ('LEAD', 20)])),
            # platform_distribution
            AsyncMock(fetchall=MagicMock(return_value=[('tiktok', 80), ('facebook', 40), ('youtube', 30)])),
            # engagement_data
            AsyncMock(fetchone=MagicMock(return_value=MagicMock(
                total_views=500000, total_likes=25000, total_shares=5000, total_saves=8000,
                avg_sentiment=0.35, avg_impact=42.5, viral_count=15, kol_count=25
            )))
        ]
        
        mock_db_session.execute.side_effect = mock_results
        
        result = await repository.get_summary_stats(project_id)
        
        assert result['total_posts'] == 150
        assert result['total_comments'] == 2500
        assert result['sentiment_distribution'] == {'POSITIVE': 80, 'NEGATIVE': 30, 'NEUTRAL': 40}
        assert result['viral_count'] == 15
        assert result['avg_impact_score'] == 42.5
        assert mock_db_session.execute.call_count == 7

    @pytest.mark.asyncio
    async def test_get_post_by_id_found(self, repository, mock_db_session):
        """Test retrieving post by ID when found."""
        post_id = "test_post_123"
        mock_post = MagicMock()
        mock_post.comments = []
        
        mock_result = AsyncMock()
        mock_result.scalars.return_value.first.return_value = mock_post
        mock_db_session.execute.return_value = mock_result
        
        result = await repository.get_post_by_id(post_id)
        
        assert result == mock_post
        mock_db_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_post_by_id_not_found(self, repository, mock_db_session):
        """Test retrieving post by ID when not found."""
        post_id = "nonexistent_post"
        
        mock_result = AsyncMock()
        mock_result.scalars.return_value.first.return_value = None
        mock_db_session.execute.return_value = mock_result
        
        result = await repository.get_post_by_id(post_id)
        
        assert result is None
        mock_db_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_crawl_errors(self, repository, mock_db_session):
        """Test crawl errors retrieval."""
        error_filters = ErrorFilters(
            project_id=UUID('12345678-1234-5678-1234-567812345678'),
            error_code="CONTENT_NOT_FOUND"
        )
        pagination = PaginationParams(page=1, page_size=10)
        
        # Mock results
        mock_errors = [MagicMock() for _ in range(3)]
        mock_count_result = AsyncMock()
        mock_count_result.scalar.return_value = 25
        
        mock_errors_result = AsyncMock()
        mock_errors_result.scalars.return_value.all.return_value = mock_errors
        
        mock_db_session.execute.side_effect = [mock_count_result, mock_errors_result]
        
        errors, total_count = await repository.get_crawl_errors(error_filters, pagination)
        
        assert len(errors) == 3
        assert total_count == 25
        assert mock_db_session.execute.call_count == 2