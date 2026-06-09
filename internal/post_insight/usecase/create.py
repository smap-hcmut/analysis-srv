from internal.model.post_insight import PostInsight
from ..type import CreatePostInsightInput
from ..repository.option import UpsertOptions
from ..repository.errors import ErrFailedToCreate


async def create(self, input: CreatePostInsightInput) -> PostInsight:
    # Route to repository.upsert(): the analysis pipeline re-processes the
    # same UAP every batch (~21 times/day per post when the scheduler runs
    # every 3 minutes), and a plain INSERT created one new row each time —
    # inflating analysis.post_insight to 21x the unique post count and
    # forcing the mart's DISTINCT ON to do a ~95% dedupe pass on every
    # refresh. Upsert by (project_id, platform, source_id) collapses those
    # repeats into a single row updated in-place.
    try:
        return await self.repository.upsert(UpsertOptions(data=input.to_dict()))
    except Exception as e:
        self.logger.error(f"internal.post_insight.usecase.create: {e}")
        raise ErrFailedToCreate(e)
