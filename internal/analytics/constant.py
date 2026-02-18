# Model version
MODEL_VERSION = "1.0.0"

# Default values for unknown/missing data
DEFAULT_EVENT_ID = "unknown"
DEFAULT_POST_ID = "unknown"
DEFAULT_PLATFORM = "unknown"

# Pipeline version template
PIPELINE_VERSION_TEMPLATE = "crawler_{platform}_v{version}"
PIPELINE_VERSION_NUMBER = 3

# Null string constant
NULL_STRING = "NULL"

# Default sentiment values for skipped posts
DEFAULT_SENTIMENT_LABEL = "NEUTRAL"
DEFAULT_SENTIMENT_SCORE = 0.0
DEFAULT_CONFIDENCE = 0.0

# Default intent value
DEFAULT_INTENT_LABEL = "DISCUSSION"

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
    "DEFAULT_EVENT_ID",
    "DEFAULT_POST_ID",
    "DEFAULT_PLATFORM",
    "PIPELINE_VERSION_TEMPLATE",
    "PIPELINE_VERSION_NUMBER",
    "NULL_STRING",
    "DEFAULT_SENTIMENT_LABEL",
    "DEFAULT_SENTIMENT_SCORE",
    "DEFAULT_CONFIDENCE",
    "DEFAULT_INTENT_LABEL",
    "DEFAULT_IMPACT_SCORE",
    "DEFAULT_RISK_LEVEL",
    "DEFAULT_IS_VIRAL",
    "DEFAULT_IS_KOL",
    "PLATFORM_UNKNOWN",
    "STATUS_SUCCESS",
    "STATUS_ERROR",
    "STATUS_SKIPPED",
]
