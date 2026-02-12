"""Use case for analyzed post operations."""

from typing import Optional

from pkg.logger.logger import Logger
from internal.model import AnalyzedPost
from ..interface import IAnalyzedPostUseCase
from ..type import CreateAnalyzedPostInput, UpdateAnalyzedPostInput
from ..repository.interface import IAnalyzedPostRepository


class AnalyzedPostUseCase(IAnalyzedPostUseCase):
    """Use case for managing analyzed posts."""

    def __init__(
        self,
        repository: IAnalyzedPostRepository,
        logger: Optional[Logger] = None,
    ):
        """Initialize use case.
        
        Args:
            repository: Repository for data access
            logger: Logger instance (optional)
        """
        self.repository = repository
        self.logger = logger

    def create(self, input_data: CreateAnalyzedPostInput) -> AnalyzedPost:
        """Create a new analyzed post record.
        
        Args:
            input_data: Data for creating analyzed post
            
        Returns:
            Created AnalyzedPost instance
        """
        if self.logger:
            self.logger.debug(f"[AnalyzedPostUseCase] Creating analyzed post")
        
        return self.repository.save(input_data.data)

    def update(self, post_id: str, input_data: UpdateAnalyzedPostInput) -> AnalyzedPost:
        """Update an existing analyzed post record.
        
        Args:
            post_id: ID of post to update
            input_data: Data for updating analyzed post
            
        Returns:
            Updated AnalyzedPost instance
        """
        if self.logger:
            self.logger.debug(f"[AnalyzedPostUseCase] Updating analyzed post: {post_id}")
        
        # Merge post_id into data
        data = input_data.data.copy()
        data["id"] = post_id
        
        return self.repository.save(data)


__all__ = ["AnalyzedPostUseCase"]
