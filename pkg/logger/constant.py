from enum import Enum


class LogLevel(str, Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARN = "WARN"
    ERROR = "ERROR"


DEFAULT_SERVICE_NAME = "analytics-engine"
DEFAULT_LEVEL = LogLevel.INFO
DEFAULT_ENABLE_CONSOLE = True
DEFAULT_COLORIZE = True

LOG_TIME_FORMAT = "YYYY-MM-DD HH:mm:ss"

LOG_FORMAT_TIME = "<green>{time:YYYY-MM-DD HH:mm:ss}</green>"
LOG_FORMAT_LEVEL = "<level>{level: <5}</level>"
LOG_FORMAT_TRACE = "<cyan>{extra[trace_id]: <16}</cyan>"
LOG_FORMAT_LOCATION = "<cyan>{file.path}</cyan>:<cyan>{line}</cyan>"
LOG_FORMAT_MESSAGE = "<level>{message}</level>"

TRACE_ID_KEY = "trace_id"
REQUEST_ID_KEY = "request_id"
