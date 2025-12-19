"""Abstract repository interface for Analytics API service."""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Optional, Tuple
from uuid import UUID

from models.database import PostAnalytics, CrawlError
from models.schemas.base import PaginationParams


class PostFilters:
    """Filter parameters for post queries."""

    def __init__(
        self,
        project_id: UUID,
        brand_name: Optional[str] = None,
        keyword: Optional[str] = None,
        platform: Optional[str] = None,
        sentiment: Optional[str] = None,
        risk_level: Optional[str] = None,
        intent: Optional[str] = None,
        is_viral: Optional[bool] = None,
        is_kol: Optional[bool] = None,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
    ):
        self.project_id = project_id
        self.brand_name = brand_name
        self.keyword = keyword
        self.platform = platform
        self.sentiment = sentiment
        self.risk_level = risk_level
        self.intent = intent
        self.is_viral = is_viral
        self.is_kol = is_kol
        self.from_date = from_date
        self.to_date = to_date


class ErrorFilters:
    """Filter parameters for crawl error queries."""

    def __init__(
        self,
        project_id: UUID,
        job_id: Optional[str] = None,
        error_code: Optional[str] = None,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
    ):
        self.project_id = project_id
        self.job_id = job_id
        self.error_code = error_code
        self.from_date = from_date
        self.to_date = to_date


class IAnalyticsApiRepository(ABC):
    """Abstract interface for Analytics API repository operations."""

    # Posts operations
    @abstractmethod
    async def get_posts(
        self,
        filters: PostFilters,
        pagination: PaginationParams,
        sort_by: str = "analyzed_at",
        sort_order: str = "desc",
    ) -> Tuple[List[PostAnalytics], int]:
        """Get paginated posts with filtering and sorting.

        Returns:
            Tuple of (posts_list, total_count)
        """
        pass

    @abstractmethod
    async def get_posts_all(
        self,
        filters: PostFilters,
        sort_by: str = "analyzed_at",
        sort_order: str = "desc",
        limit: int = 1000,
    ) -> Tuple[List[PostAnalytics], int]:
        """Get all posts without pagination (for export).

        Returns:
            Tuple of (posts_list, total_count)
        """
        pass

    @abstractmethod
    async def get_post_by_id(self, post_id: str) -> Optional[PostAnalytics]:
        """Get post by ID with all details including comments."""
        pass

    # Summary operations
    @abstractmethod
    async def get_summary_stats(
        self,
        project_id: UUID,
        brand_name: Optional[str] = None,
        keyword: Optional[str] = None,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
    ) -> dict:
        """Get aggregated summary statistics."""
        pass

    # Trends operations
    @abstractmethod
    async def get_trends_data(
        self,
        project_id: UUID,
        granularity: str,  # "day", "week", "month"
        from_date: datetime,
        to_date: datetime,
        brand_name: Optional[str] = None,
        keyword: Optional[str] = None,
    ) -> List[dict]:
        """Get time-series trends data."""
        pass

    # Keywords operations
    @abstractmethod
    async def get_top_keywords(
        self,
        project_id: UUID,
        limit: int = 20,
        brand_name: Optional[str] = None,
        keyword: Optional[str] = None,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
    ) -> List[dict]:
        """Get top keywords with sentiment analysis."""
        pass

    # Alerts operations
    @abstractmethod
    async def get_alert_posts(
        self,
        project_id: UUID,
        limit: int = 10,
        brand_name: Optional[str] = None,
        keyword: Optional[str] = None,
    ) -> dict:
        """Get posts requiring attention (critical, viral, crisis)."""
        pass

    # Errors operations
    @abstractmethod
    async def get_crawl_errors(
        self,
        filters: ErrorFilters,
        pagination: PaginationParams,
    ) -> Tuple[List[CrawlError], int]:
        """Get paginated crawl errors with filtering."""
        pass

    # Health check
    @abstractmethod
    async def health_check(self) -> bool:
        """Check database connectivity."""
        pass
