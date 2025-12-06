"""Constants for Analytics Engine."""

from enum import Enum


class ErrorCode(str, Enum):
    """Crawler error codes - 17 codes across 7 categories."""

    # Rate limiting (3 codes)
    RATE_LIMITED = "RATE_LIMITED"
    AUTH_FAILED = "AUTH_FAILED"
    ACCESS_DENIED = "ACCESS_DENIED"

    # Content (3 codes)
    CONTENT_REMOVED = "CONTENT_REMOVED"
    CONTENT_NOT_FOUND = "CONTENT_NOT_FOUND"
    CONTENT_UNAVAILABLE = "CONTENT_UNAVAILABLE"

    # Network (4 codes)
    NETWORK_ERROR = "NETWORK_ERROR"
    TIMEOUT = "TIMEOUT"
    CONNECTION_REFUSED = "CONNECTION_REFUSED"
    DNS_ERROR = "DNS_ERROR"

    # Parsing (3 codes)
    PARSE_ERROR = "PARSE_ERROR"
    INVALID_URL = "INVALID_URL"
    INVALID_RESPONSE = "INVALID_RESPONSE"

    # Media (3 codes)
    MEDIA_DOWNLOAD_FAILED = "MEDIA_DOWNLOAD_FAILED"
    MEDIA_TOO_LARGE = "MEDIA_TOO_LARGE"
    MEDIA_FORMAT_ERROR = "MEDIA_FORMAT_ERROR"

    # Storage (3 codes)
    STORAGE_ERROR = "STORAGE_ERROR"
    UPLOAD_FAILED = "UPLOAD_FAILED"
    DATABASE_ERROR = "DATABASE_ERROR"

    # Generic (2 codes)
    UNKNOWN_ERROR = "UNKNOWN_ERROR"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class ErrorCategory(str, Enum):
    """Error categories for grouping error codes."""

    RATE_LIMITING = "rate_limiting"
    CONTENT = "content"
    NETWORK = "network"
    PARSING = "parsing"
    MEDIA = "media"
    STORAGE = "storage"
    GENERIC = "generic"


# Mapping from ErrorCode to ErrorCategory
ERROR_CODE_TO_CATEGORY: dict[ErrorCode, ErrorCategory] = {
    # Rate limiting
    ErrorCode.RATE_LIMITED: ErrorCategory.RATE_LIMITING,
    ErrorCode.AUTH_FAILED: ErrorCategory.RATE_LIMITING,
    ErrorCode.ACCESS_DENIED: ErrorCategory.RATE_LIMITING,
    # Content
    ErrorCode.CONTENT_REMOVED: ErrorCategory.CONTENT,
    ErrorCode.CONTENT_NOT_FOUND: ErrorCategory.CONTENT,
    ErrorCode.CONTENT_UNAVAILABLE: ErrorCategory.CONTENT,
    # Network
    ErrorCode.NETWORK_ERROR: ErrorCategory.NETWORK,
    ErrorCode.TIMEOUT: ErrorCategory.NETWORK,
    ErrorCode.CONNECTION_REFUSED: ErrorCategory.NETWORK,
    ErrorCode.DNS_ERROR: ErrorCategory.NETWORK,
    # Parsing
    ErrorCode.PARSE_ERROR: ErrorCategory.PARSING,
    ErrorCode.INVALID_URL: ErrorCategory.PARSING,
    ErrorCode.INVALID_RESPONSE: ErrorCategory.PARSING,
    # Media
    ErrorCode.MEDIA_DOWNLOAD_FAILED: ErrorCategory.MEDIA,
    ErrorCode.MEDIA_TOO_LARGE: ErrorCategory.MEDIA,
    ErrorCode.MEDIA_FORMAT_ERROR: ErrorCategory.MEDIA,
    # Storage
    ErrorCode.STORAGE_ERROR: ErrorCategory.STORAGE,
    ErrorCode.UPLOAD_FAILED: ErrorCategory.STORAGE,
    ErrorCode.DATABASE_ERROR: ErrorCategory.STORAGE,
    # Generic
    ErrorCode.UNKNOWN_ERROR: ErrorCategory.GENERIC,
    ErrorCode.INTERNAL_ERROR: ErrorCategory.GENERIC,
}

# Retryable error codes
RETRYABLE_ERROR_CODES: set[ErrorCode] = {
    ErrorCode.RATE_LIMITED,
    ErrorCode.AUTH_FAILED,
    ErrorCode.ACCESS_DENIED,
    ErrorCode.NETWORK_ERROR,
    ErrorCode.TIMEOUT,
    ErrorCode.CONNECTION_REFUSED,
    ErrorCode.DNS_ERROR,
    ErrorCode.STORAGE_ERROR,
    ErrorCode.UPLOAD_FAILED,
    ErrorCode.DATABASE_ERROR,
}

# Permanent error codes (no retry)
PERMANENT_ERROR_CODES: set[ErrorCode] = {
    ErrorCode.CONTENT_REMOVED,
    ErrorCode.CONTENT_NOT_FOUND,
    ErrorCode.CONTENT_UNAVAILABLE,
    ErrorCode.PARSE_ERROR,
    ErrorCode.INVALID_URL,
    ErrorCode.INVALID_RESPONSE,
    ErrorCode.MEDIA_DOWNLOAD_FAILED,
    ErrorCode.MEDIA_TOO_LARGE,
    ErrorCode.MEDIA_FORMAT_ERROR,
}


def categorize_error(error_code: str) -> ErrorCategory:
    """Categorize an error code string into its category.

    Args:
        error_code: Error code string (e.g., "RATE_LIMITED")

    Returns:
        ErrorCategory for the given error code, defaults to GENERIC if unknown.
    """
    try:
        code = ErrorCode(error_code)
        return ERROR_CODE_TO_CATEGORY.get(code, ErrorCategory.GENERIC)
    except ValueError:
        return ErrorCategory.GENERIC


def is_retryable_error(error_code: str) -> bool:
    """Check if an error code is retryable.

    Args:
        error_code: Error code string

    Returns:
        True if the error is retryable, False otherwise.
    """
    try:
        code = ErrorCode(error_code)
        return code in RETRYABLE_ERROR_CODES
    except ValueError:
        return False
