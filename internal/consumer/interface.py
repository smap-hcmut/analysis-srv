from typing import Protocol, runtime_checkable


@runtime_checkable
class IConsumerServer(Protocol):
    async def start(self) -> None:
        ...

    async def shutdown(self) -> None:
        ...

    def is_running(self) -> bool:
        ...


__all__ = ["IConsumerServer"]
