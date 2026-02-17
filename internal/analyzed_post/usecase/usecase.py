"""Use case for analyzed post operations.

Convention: UseCase class delegates to method files.
Each public method is implemented in its own file.
"""

from typing import Optional

from pkg.logger.logger import Logger
from internal.model import AnalyzedPost
from ..interface import IAnalyzedPostUseCase
from ..type import CreateAnalyzedPostInput, UpdateAnalyzedPostInput
from ..repository.interface import IAnalyzedPostRepository

# Import method implementations
from .create import create as _create
from .update import update as _update


class AnalyzedPostUseCase(IAnalyzedPostUseCase):
    """Use case for managing analyzed posts.

    Convention: implUseCase struct (private) with injected dependencies.
    """

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

    async def create(self, input_data: CreateAnalyzedPostInput) -> AnalyzedPost:
        """Create a new analyzed post record."""
        return await _create(self, input_data)

    async def update(self, post_id: str, input_data: UpdateAnalyzedPostInput) -> AnalyzedPost:
        """Update an existing analyzed post record."""
        return await _update(self, post_id, input_data)


__all__ = ["AnalyzedPostUseCase"]
