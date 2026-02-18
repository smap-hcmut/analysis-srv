from typing import List, Optional, Protocol, runtime_checkable

from internal.model.post_insight import PostInsight
from .option import (
    CreateOptions,
    UpsertOptions,
    GetOneOptions,
    ListOptions,
    DeleteOptions,
)


@runtime_checkable
class IPostInsightRepository(Protocol):
    async def create(self, opt: CreateOptions) -> PostInsight: ...
    async def upsert(self, opt: UpsertOptions) -> PostInsight: ...
    async def detail(self, id: str) -> Optional[PostInsight]: ...
    async def get_one(self, opt: GetOneOptions) -> Optional[PostInsight]: ...
    async def list(self, opt: ListOptions) -> List[PostInsight]: ...
    async def delete(self, opt: DeleteOptions) -> bool: ...


__all__ = ["IPostInsightRepository"]
