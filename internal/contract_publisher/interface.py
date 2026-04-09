from typing import Protocol, runtime_checkable

from internal.model.uap import UAPRecord
from internal.model.insight_message import InsightMessage
from .type import RunContext, PublishOutput


@runtime_checkable
class IContractPublisher(Protocol):
    """Interface for the contract-compliant Kafka publisher.

    publish_one() is called per-record inside AnalyticsProcess.
    flush()       is called to drain the buffer and publish all 3 topics.
    close()       ensures a final flush on shutdown.
    """

    async def publish_one(
        self,
        uap: UAPRecord,
        msg: InsightMessage,
    ) -> None:
        """Buffer one document. May auto-flush if batch_size is reached."""
        ...

    async def flush(self, ctx: RunContext | None = None) -> PublishOutput:
        """Drain buffer and publish batch.completed → insights.published → report.digest."""
        ...

    async def close(self) -> None:
        """Flush any remaining buffered documents on shutdown."""
        ...


__all__ = ["IContractPublisher"]
