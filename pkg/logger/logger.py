import sys
from typing import Optional, Iterator, Protocol, runtime_checkable
from contextvars import ContextVar
from contextlib import contextmanager
from loguru import logger as _loguru_logger  # type: ignore

from .constant import *
from .type import LoggerConfig

# Trace ID context variable (thread-safe, async-safe)
_trace_id_var: ContextVar[Optional[str]] = ContextVar(TRACE_ID_KEY, default=None)
_request_id_var: ContextVar[Optional[str]] = ContextVar(REQUEST_ID_KEY, default=None)


@runtime_checkable
class ILogger(Protocol):
    """Protocol defining the Logger interface."""

    def trace_context(
        self, trace_id: Optional[str] = None, request_id: Optional[str] = None
    ) -> Iterator[None]: ...

    def set_trace_id(self, trace_id: str) -> None: ...

    def get_trace_id(self) -> Optional[str]: ...

    def set_request_id(self, request_id: str) -> None: ...

    def get_request_id(self) -> Optional[str]: ...

    def debug(self, message: str, **kwargs) -> None: ...

    def info(self, message: str, **kwargs) -> None: ...

    def warning(self, message: str, **kwargs) -> None: ...

    def error(self, message: str, **kwargs) -> None: ...

    def critical(self, message: str, **kwargs) -> None: ...

    def exception(self, message: str, **kwargs) -> None: ...

    def bind(self, **kwargs) -> _loguru_logger: ...  # type: ignore


class Logger(ILogger):
    """Logger wrapper with trace ID support.

    Features:
    - Explicit initialization with config
    - Trace ID tracking via contextvars
    - Structured logging
    - Console output only (Cloud Native)

    Usage:
        # Initialize in main()
        config = LoggerConfig(level="INFO")
        logger = Logger(config)
        # Setup is done in __init__

        # Use in other modules (pass logger instance or trace_id context)
        with logger.trace_context(trace_id="req_123"):
            logger.info("Processing request")
    """

    def __init__(self, config: LoggerConfig):
        """Initialize logger with configuration.

        Args:
            config: Logger configuration
        """
        self.config = config
        self._loguru = _loguru_logger

        # Remove default handler
        self._loguru.remove()

        # Add console handler
        if self.config.enable_console:
            self._add_console_handler()

    def _add_console_handler(self) -> None:
        """Add console handler with colors and trace ID."""

        def format_record(record):
            """Add trace_id to record."""
            trace_id = _trace_id_var.get()
            request_id = _request_id_var.get()

            # Add trace_id to extra
            record["extra"][TRACE_ID_KEY] = trace_id or ""
            if request_id:
                record["extra"][REQUEST_ID_KEY] = request_id

            return True

        # Format with trace_id
        format_str = f"{LOG_FORMAT_TIME} | {LOG_FORMAT_LEVEL} | "

        # Add trace_id if present
        # Note: loguru format string for extra fields
        format_str += LOG_FORMAT_TRACE + " | " if f"{{extra[{TRACE_ID_KEY}]}}" else ""

        format_str += f"{LOG_FORMAT_LOCATION} - {LOG_FORMAT_MESSAGE}"

        self._loguru.add(
            sys.stdout,
            colorize=self.config.colorize,
            format=format_str,
            level=self.config.level.value,  # Use enum value
            filter=format_record,
        )

    @contextmanager
    def trace_context(
        self, trace_id: Optional[str] = None, request_id: Optional[str] = None
    ):
        """Context manager for trace ID.

        Args:
            trace_id: Trace ID for distributed tracing
            request_id: Request ID for request tracking

        Usage:
            with logger.trace_context(trace_id="req_123"):
                logger.info("Processing")  # Auto includes trace_id
        """
        # Save previous values
        prev_trace_id = _trace_id_var.get()
        prev_request_id = _request_id_var.get()

        # Set new values
        if trace_id:
            _trace_id_var.set(trace_id)
        if request_id:
            _request_id_var.set(request_id)

        try:
            yield
        finally:
            # Restore previous values
            _trace_id_var.set(prev_trace_id)
            _request_id_var.set(prev_request_id)

    def set_trace_id(self, trace_id: str) -> None:
        """Set trace ID for current context.

        Args:
            trace_id: Trace ID to set
        """
        _trace_id_var.set(trace_id)

    def get_trace_id(self) -> Optional[str]:
        """Get current trace ID.

        Returns:
            Current trace ID or None
        """
        return _trace_id_var.get()

    def set_request_id(self, request_id: str) -> None:
        """Set request ID for current context.

        Args:
            request_id: Request ID to set
        """
        _request_id_var.set(request_id)

    def get_request_id(self) -> Optional[str]:
        """Get current request ID.

        Returns:
            Current request ID or None
        """
        return _request_id_var.get()

    def debug(self, message: str, **kwargs) -> None:
        """Log debug message."""
        self._loguru.debug(message, **kwargs)

    def info(self, message: str, **kwargs) -> None:
        """Log info message."""
        self._loguru.info(message, **kwargs)

    def warning(self, message: str, **kwargs) -> None:
        """Log warning message."""
        self._loguru.warning(message, **kwargs)

    def error(self, message: str, **kwargs) -> None:
        """Log error message."""
        self._loguru.error(message, **kwargs)

    def critical(self, message: str, **kwargs) -> None:
        """Log critical message."""
        self._loguru.critical(message, **kwargs)

    def exception(self, message: str, **kwargs) -> None:
        """Log exception with traceback."""
        self._loguru.exception(message, **kwargs)

    def bind(self, **kwargs) -> _loguru_logger:  # type: ignore
        """Bind context to logger.

        Returns:
            Bound logger instance from loguru
        """
        return self._loguru.bind(**kwargs)


__all__ = [
    "Logger",
    "ILogger",
    "LoggerConfig",
]
