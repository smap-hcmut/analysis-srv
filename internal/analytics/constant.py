"""Constants for Analytics Pipeline."""

# Model version
MODEL_VERSION = "1.0.0"

# Default sentiment values for skipped posts
DEFAULT_SENTIMENT_LABEL = "NEUTRAL"
DEFAULT_SENTIMENT_SCORE = 0.0
DEFAULT_CONFIDENCE = 0.0

# Default impact values
DEFAULT_IMPACT_SCORE = 0.0
DEFAULT_RISK_LEVEL = "LOW"
DEFAULT_IS_VIRAL = False
DEFAULT_IS_KOL = False

# Platform normalization
PLATFORM_UNKNOWN = "UNKNOWN"

# Processing status
STATUS_SUCCESS = "success"
STATUS_ERROR = "error"
STATUS_SKIPPED = "skipped"

__all__ = [
    "MODEL_VERSION",
    "DEFAULT_SENTIMENT_LABEL",
    "DEFAULT_SENTIMENT_SCORE",
    "DEFAULT_CONFIDENCE",
    "DEFAULT_IMPACT_SCORE",
    "DEFAULT_RISK_LEVEL",
    "DEFAULT_IS_VIRAL",
    "DEFAULT_IS_KOL",
    "PLATFORM_UNKNOWN",
    "STATUS_SUCCESS",
    "STATUS_ERROR",
    "STATUS_SKIPPED",
]
