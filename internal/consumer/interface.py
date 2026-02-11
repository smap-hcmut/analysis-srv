from typing import Protocol, runtime_checkable


@runtime_checkable
class IConsumerServer(Protocol):
    """Protocol defining the consumer server interface.

    This interface defines the contract for consumer server implementations.
    Any class implementing this protocol must provide these methods.
    """

    async def start(self) -> None:
        """Start the consumer server.

        This method should:
        1. Connect to message broker
        2. Register message handlers
        3. Start consuming messages

        Raises:
            Exception: If server fails to start
        """
        ...

    async def shutdown(self) -> None:
        """Shutdown the consumer server gracefully.

        This method should:
        1. Stop consuming new messages
        2. Wait for in-flight messages to complete
        3. Close all connections
        """
        ...

    def is_running(self) -> bool:
        """Check if server is running.

        Returns:
            True if server is running, False otherwise
        """
        ...


__all__ = ["IConsumerServer"]
