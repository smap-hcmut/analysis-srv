from typing import Any, Optional, Protocol, runtime_checkable

from .type import Input, Output

from internal.model.uap import UAPRecord
from internal.model.insight_message import InsightMessage


@runtime_checkable
class IAnalyticsUseCase(Protocol):
    async def process(self, input_data: Input) -> Output: ...


@runtime_checkable
class IAnalyticsPublisher(Protocol):
    """Legacy publisher interface (smap.analytics.output — kept for compatibility)."""

    async def publish(self, enriched: InsightMessage) -> None: ...

    async def flush(self) -> None: ...


@runtime_checkable
class IContractPublisher(Protocol):
    """Contract-compliant publisher for 3 knowledge-srv topics."""

    async def publish_one(
        self,
        uap: UAPRecord,
        msg: InsightMessage,
        insight_cards: Optional[list[Any]] = None,
    ) -> None: ...

    async def flush(self, ctx: Any = None) -> Any: ...

    async def close(self) -> None: ...


__all__ = ["IAnalyticsUseCase", "IAnalyticsPublisher", "IContractPublisher"]
