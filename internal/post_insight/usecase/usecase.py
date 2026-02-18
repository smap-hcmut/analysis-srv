from typing import Optional

from pkg.logger.logger import Logger
from internal.model.post_insight import PostInsight

from ..repository.interface import IPostInsightRepository
from ..interface import IPostInsightUseCase
from ..type import CreatePostInsightInput, UpdatePostInsightInput
from .create import create as _create
from .update import update as _update


class PostInsightUseCase(IPostInsightUseCase):
    def __init__(
        self,
        repository: IPostInsightRepository,
        logger: Optional[Logger] = None,
    ) -> None:
        self.repository = repository
        self.logger = logger

    async def create(self, input_data: CreatePostInsightInput) -> PostInsight:
        return await _create(self, input_data)

    async def update(
        self, post_id: str, input_data: UpdatePostInsightInput
    ) -> PostInsight:
        return await _update(self, post_id, input_data)
