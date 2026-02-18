from dataclasses import dataclass, field
from .constant import *


@dataclass
class Config:
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
    keyword: str
    aspect: str = DEFAULT_ASPECT
    position: int | None = None
    score: float = 1.0
    source: str = "DICT"


@dataclass
class SentimentResult:
    label: str
    score: float
    confidence: float
    probabilities: dict[str, float] = field(default_factory=dict)
    rating: int = DEFAULT_RATING
    error: str | None = None


@dataclass
class AspectSentiment:
    label: str
    score: float
    confidence: float
    mentions: int
    keywords: list[str]
    rating: int = DEFAULT_RATING


@dataclass
class Output:
    overall: SentimentResult
    aspects: dict[str, AspectSentiment] = field(default_factory=dict)


@dataclass
class Input:
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
