"""outbox/usecase/new.py — factory for OutboxUseCase."""

from internal.outbox.usecase.usecase import OutboxUseCase


def new_outbox_usecase() -> OutboxUseCase:
    return OutboxUseCase()


__all__ = ["new_outbox_usecase"]
