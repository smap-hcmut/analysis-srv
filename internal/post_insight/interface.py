from typing import Protocol, runtime_checkable

from internal.model.post_insight import PostInsight
from .type import CreatePostInsightInput, UpdatePostInsightInput


@runtime_checkable
class IPostInsightUseCase(Protocol):
    async def create(self, input_data: CreatePostInsightInput) -> PostInsight:
        ...

    async def update(
        self, post_id: str, input_data: UpdatePostInsightInput
    ) -> PostInsight:
        ...


__all__ = ["IPostInsightUseCase"]
