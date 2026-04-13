"""outbox/interface.py — IOutboxUseCase protocol."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from internal.outbox.type import OutboxRecord, RelayResult


class IOutboxUseCase(ABC):
    @abstractmethod
    def write(self, record: "OutboxRecord", conn: object) -> None:
        """Persist an outbox record within the caller's DB connection/transaction."""

    @abstractmethod
    def relay(self, conn: object, producer: object) -> "RelayResult":
        """Poll pending outbox records and publish them to Kafka."""


__all__ = ["IOutboxUseCase"]
