from dataclasses import dataclass, field
from .constant import *


@dataclass
class Config:
    """Configuration for sentiment analysis."""

    context_window_size: int = DEFAULT_CONTEXT_WINDOW_SIZE
    threshold_positive: float = DEFAULT_THRESHOLD_POSITIVE
    threshold_negative: float = DEFAULT_THRESHOLD_NEGATIVE

    def __post_init__(self):
        if self.context_window_size <= 0:
            raise ValueError("context_window_size must be > 0")
        if not -1.0 <= self.threshold_negative < self.threshold_positive <= 1.0:
            raise ValueError(
                "thresholds must satisfy: -1.0 <= threshold_negative < threshold_positive <= 1.0"
            )


@dataclass
class KeywordInput:
    """Keyword input for aspect-based sentiment analysis."""

    keyword: str
    aspect: str = DEFAULT_ASPECT
    position: int | None = None
    score: float = 1.0
    source: str = "DICT"


@dataclass
class SentimentResult:
    """Single sentiment analysis result."""

    label: str
    score: float
    confidence: float
    probabilities: dict[str, float] = field(default_factory=dict)
    rating: int = DEFAULT_RATING
    error: str | None = None


@dataclass
class AspectSentiment:
    """Aspect-level sentiment result."""

    label: str
    score: float
    confidence: float
    mentions: int
    keywords: list[str]
    rating: int = DEFAULT_RATING


@dataclass
class Output:
    """Output of sentiment analysis.

    Attributes:
        overall: Overall sentiment for full text
        aspects: Aspect-level sentiments (empty dict if no keywords)
    """

    overall: SentimentResult
    aspects: dict[str, AspectSentiment] = field(default_factory=dict)


@dataclass
class Input:
    """Input structure for sentiment analysis."""

    text: str
    keywords: list[KeywordInput] = field(default_factory=list)


__all__ = [
    "Config",
    "KeywordInput",
    "SentimentResult",
    "AspectSentiment",
    "Output",
    "Input",
]
