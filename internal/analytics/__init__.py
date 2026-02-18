"""Analytics Pipeline Domain.

This domain orchestrates the full analytics pipeline for social media posts.
"""

from .constant import *
from .interface import IAnalyticsPipeline
from .type import (
    Config,
    Input,
    Output,
    AnalyticsResult,
)
from .errors import (
    ErrPipelineProcessing,
    ErrInvalidInput,
    ErrPreprocessingFailed,
    ErrPersistenceFailed,
)

# Import factory functions
from .usecase.new import New as NewAnalyticsPipeline
from .delivery.kafka.consumer.new import new_kafka_handler as NewAnalyticsHandler

__all__ = [
    # Interface
    "IAnalyticsPipeline",
    # Types
    "Config",
    "Input",
    "Output",
    "AnalyticsResult",
    # Errors
    "ErrPipelineProcessing",
    "ErrInvalidInput",
    "ErrPreprocessingFailed",
    "ErrPersistenceFailed",
    # Factory functions
    "NewAnalyticsPipeline",
    "NewAnalyticsHandler",
    # Constants
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
