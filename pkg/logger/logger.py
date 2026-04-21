import sys
import json
import email.utils
from datetime import timezone, timedelta
from typing import Optional, Iterator
from contextvars import ContextVar
from contextlib import contextmanager
from loguru import logger as _loguru_logger  # type: ignore

from .interface import ILogger
from .constant import (
    DEFAULT_SERVICE_NAME,
    DEFAULT_LEVEL,
    DEFAULT_ENABLE_CONSOLE,
    DEFAULT_COLORIZE,
    DEFAULT_JSON_OUTPUT,
    LOG_FORMAT_TIME,
    LOG_FORMAT_LEVEL,
    LOG_FORMAT_TRACE,
    LOG_FORMAT_LOCATION,
    LOG_FORMAT_MESSAGE,
    TRACE_ID_KEY,
    REQUEST_ID_KEY,
)
from .type import LoggerConfig

# Trace ID context variable (thread-safe, async-safe)
_trace_id_var: ContextVar[Optional[str]] = ContextVar(TRACE_ID_KEY, default=None)
_request_id_var: ContextVar[Optional[str]] = ContextVar(REQUEST_ID_KEY, default=None)

# Business context variables — used for log enrichment (not tracing)
_project_id_var: ContextVar[Optional[str]] = ContextVar("project_id", default=None)
_campaign_id_var: ContextVar[Optional[str]] = ContextVar("campaign_id", default=None)


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
        from pathlib import Path

        self.config = config
        self._loguru = _loguru_logger

        # Cache workspace root (computed once)
        self.workspace_root = Path.cwd()

        # Cache for relative paths (avoid recomputing for same files)
        self._path_cache: dict[str, str] = {}

        # Remove default handler
        self._loguru.remove()

        # Add console handler
        if self.config.enable_console:
            self._add_console_handler()

    def _add_console_handler(self) -> None:
        """Add console handler with colors and trace ID."""

        # Production JSON mode: structured output for central log processing
        if self.config.json_output:
            import os
            import json

            service_name = os.getenv("CONTAINER_NAME", "analysis-srv")

            ict_tz = timezone(timedelta(hours=7))

            def custom_json_sink(message):
                record = message.record
                dt = record["time"].astimezone(ict_tz)
                log_dict = {
                    "timestamp": email.utils.format_datetime(dt),
                    "trace_id": record["extra"].get(
                        "trace_id", _trace_id_var.get() or ""
                    ),
                    "level": record["level"].name.lower(),
                    "caller": f"{record['file'].name}:{record['line']}",
                    "message": record["message"],
                    "service": service_name,
                }
                # Add business context fields for log enrichment
                project_id = _project_id_var.get()
                if project_id:
                    log_dict["project_id"] = project_id
                campaign_id = _campaign_id_var.get()
                if campaign_id:
                    log_dict["campaign_id"] = campaign_id
                # Include extra fields
                for key, value in record["extra"].items():
                    if key != "trace_id" and key not in log_dict:
                        log_dict[key] = value

                print(json.dumps(log_dict), flush=True)

            self._loguru.add(
                custom_json_sink,
                level=self.config.level.value,
            )
            return

        from pathlib import Path

        # Capture instance variables in closure
        workspace_root = self.workspace_root
        path_cache = self._path_cache

        def format_record(record):
            """Add trace_id and relative path to record."""
            trace_id = _trace_id_var.get()
            request_id = _request_id_var.get()

            # Add trace_id to extra (empty string if not set)
            record["extra"][TRACE_ID_KEY] = trace_id or ""
            if request_id:
                record["extra"][REQUEST_ID_KEY] = request_id

            # Add business context fields
            project_id = _project_id_var.get()
            if project_id:
                record["extra"]["project_id"] = project_id
            campaign_id = _campaign_id_var.get()
            if campaign_id:
                record["extra"]["campaign_id"] = campaign_id

            # Get or compute relative path (with caching)
            abs_path = record["file"].path
            if abs_path not in path_cache:
                try:
                    file_path = Path(abs_path)
                    relative_path = file_path.relative_to(workspace_root)
                    path_cache[abs_path] = str(relative_path)
                except (ValueError, AttributeError):
                    # Fallback to filename if relative path fails
                    path_cache[abs_path] = record["file"].name

            record["extra"]["relative_path"] = path_cache[abs_path]
            return True

        # Build format string based on config
        format_str = f"{LOG_FORMAT_TIME} | {LOG_FORMAT_LEVEL}"

        # Add trace_id if enabled
        if self.config.enable_trace_id:
            format_str += f" | {LOG_FORMAT_TRACE}"

        # Add location (relative path) and message
        format_str += (
            " | <cyan>{extra[relative_path]}</cyan>:<cyan>{line}</cyan> - {message}"
        )

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
        self._loguru.opt(depth=1).debug(message, **kwargs)

    def info(self, message: str, **kwargs) -> None:
        """Log info message."""
        self._loguru.opt(depth=1).info(message, **kwargs)

    def warn(self, message: str, **kwargs) -> None:
        """Log warning message."""
        self._loguru.opt(depth=1).warning(message, **kwargs)

    def error(self, message: str, **kwargs) -> None:
        """Log error message."""
        self._loguru.opt(depth=1).error(message, **kwargs)

    def exception(self, message: str, **kwargs) -> None:
        """Log exception with traceback."""
        self._loguru.opt(depth=1).exception(message, **kwargs)

    def bind(self, **kwargs) -> _loguru_logger:  # type: ignore
        """Bind context to logger.

        Returns:
            Bound logger instance from loguru
        """
        return self._loguru.bind(**kwargs)


__all__ = [
    "Logger",
    "LoggerConfig",
]


# Module-level context functions for direct access without a Logger instance


def set_trace_id(trace_id: str) -> None:
    """Set trace_id in current context."""
    _trace_id_var.set(trace_id)


def get_trace_id() -> Optional[str]:
    """Get current trace_id from context."""
    return _trace_id_var.get()


def set_project_id(project_id: str) -> None:
    """Set project_id in current context."""
    _project_id_var.set(project_id)


def get_project_id() -> Optional[str]:
    """Get current project_id from context."""
    return _project_id_var.get()


def clear_project_id() -> None:
    """Clear project_id from current context."""
    _project_id_var.set(None)


def set_campaign_id(campaign_id: str) -> None:
    """Set campaign_id in current context."""
    _campaign_id_var.set(campaign_id)


def get_campaign_id() -> Optional[str]:
    """Get current campaign_id from context."""
    return _campaign_id_var.get()


def clear_campaign_id() -> None:
    """Clear campaign_id from current context."""
    _campaign_id_var.set(None)
