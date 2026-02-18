from internal.model.post_insight import PostInsight
from ..type import CreatePostInsightInput
from ..repository.option import CreateOptions
from ..repository.errors import ErrFailedToCreate


async def create(self, input: CreatePostInsightInput) -> PostInsight:
    try:
        return await self.repository.create(CreateOptions(data=input.to_dict()))
    except Exception as e:
        self.logger.error(f"internal.post_insight.usecase.create: {e}")
        raise ErrFailedToCreate(e)
