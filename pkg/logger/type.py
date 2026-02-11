from dataclasses import dataclass, field
from .constant import *


@dataclass
class LoggerConfig:
    """Logger configuration.

    Attributes:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        enable_console: Enable console output
        colorize: Enable colored console output
        service_name: Service name for structured logging
    """

    level: LogLevel = DEFAULT_LEVEL
    enable_console: bool = DEFAULT_ENABLE_CONSOLE
    colorize: bool = DEFAULT_COLORIZE
    service_name: str = DEFAULT_SERVICE_NAME

    def __post_init__(self):
        """Validate configuration."""
        # Validate log level
        if isinstance(self.level, str):
            try:
                # Convert string to enum
                self.level = LogLevel(self.level.upper())
            except ValueError:
                valid_levels = [l.value for l in LogLevel]
                raise ValueError(
                    f"Invalid log level: {self.level}. Must be one of {valid_levels}"
                )
