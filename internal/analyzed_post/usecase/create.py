"""Create method for analyzed post use case.

Convention: Each public interface method gets its own file.
"""

from internal.model import AnalyzedPost
from ..type import CreateAnalyzedPostInput
from ..repository.option import CreateOptions


async def create(self, input_data: CreateAnalyzedPostInput) -> AnalyzedPost:
    """Create a new analyzed post record.

    Args:
        input_data: Data for creating analyzed post

    Returns:
        Created AnalyzedPost instance
    """
    if self.logger:
        self.logger.debug("[AnalyzedPostUseCase] Creating analyzed post")

    return await self.repository.create(CreateOptions(data=input_data.data))
