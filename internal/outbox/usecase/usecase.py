"""outbox/usecase/usecase.py — OutboxUseCase."""

from __future__ import annotations

from internal.outbox.interface import IOutboxUseCase
from internal.outbox.type import OutboxRecord, RelayResult
from internal.outbox.usecase.write_outbox import write_outbox_record
from internal.outbox.usecase.relay_outbox import relay_pending_records


class OutboxUseCase(IOutboxUseCase):
    def write(self, record: OutboxRecord, conn: object) -> None:
        write_outbox_record(conn, record)

    def relay(self, conn: object, producer: object) -> RelayResult:
        return relay_pending_records(conn, producer)


__all__ = ["OutboxUseCase"]
