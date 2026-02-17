"""Update method for analyzed post use case.

Convention: Each public interface method gets its own file.
"""

from internal.model import AnalyzedPost
from ..type import UpdateAnalyzedPostInput
from ..repository.option import UpsertOptions


async def update(self, post_id: str, input_data: UpdateAnalyzedPostInput) -> AnalyzedPost:
    """Update an existing analyzed post record.

    Args:
        post_id: ID of post to update
        input_data: Data for updating analyzed post

    Returns:
        Updated AnalyzedPost instance
    """
    if self.logger:
        self.logger.debug(f"[AnalyzedPostUseCase] Updating analyzed post: {post_id}")

    data = input_data.data.copy()
    data["id"] = post_id

    return await self.repository.upsert(UpsertOptions(data=data))
