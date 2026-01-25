"""Repository interface - Abstract base class for data access."""

from abc import ABC, abstractmethod
from typing import Optional, List
from models.database import PostAnalytics


class IAnalyticsRepository(ABC):
    """Interface for analytics repository operations."""

    @abstractmethod
    async def create(self, analytics: PostAnalytics) -> PostAnalytics:
        """Create a new analytics record."""
        pass

    @abstractmethod
    async def get_by_id(self, analytics_id: str) -> Optional[PostAnalytics]:
        """Get analytics by ID."""
        pass

    @abstractmethod
    async def get_by_project(self, project_id: str) -> List[PostAnalytics]:
        """Get all analytics for a project."""
        pass

    @abstractmethod
    async def update(self, analytics: PostAnalytics) -> PostAnalytics:
        """Update an analytics record."""
        pass

    @abstractmethod
    async def delete(self, analytics_id: str) -> bool:
        """Delete an analytics record."""
        pass
