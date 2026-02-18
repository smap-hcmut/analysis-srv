from typing import Protocol, runtime_checkable

from .type import Input, Output


from internal.model.insight_message import InsightMessage


@runtime_checkable
class IAnalyticsUseCase(Protocol):
    async def process(self, input_data: Input) -> Output:
        ...


@runtime_checkable
class IAnalyticsPublisher(Protocol):
    async def publish(self, enriched: InsightMessage) -> None:
        ...

    async def flush(self) -> None: ...

__all__ = ["IAnalyticsUseCase", "IAnalyticsPublisher"]
