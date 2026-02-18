from internal.model.post_insight import PostInsight
from ..type import UpdatePostInsightInput
from ..repository.option import UpsertOptions
from ..repository.errors import ErrFailedToUpdate

async def update(self, input: UpdatePostInsightInput) -> PostInsight:
    try:
        return await self.repository.upsert(UpsertOptions(data=input.to_dict()))
    except Exception as e:
        self.logger.error("internal.post_insight.usecase.update: %s", e)
        raise ErrFailedToUpdate(e)
