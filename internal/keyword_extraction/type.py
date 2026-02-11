from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from .constant import *


@dataclass
class Config:
    """Configuration for keyword extraction."""

    aspect_dictionary_path: str | None = DEFAULT_ASPECT_DICTIONARY_PATH
    enable_ai: bool = DEFAULT_ENABLE_AI
    ai_threshold: int = DEFAULT_AI_THRESHOLD
    max_keywords: int = DEFAULT_MAX_KEYWORDS

    def __post_init__(self):
        if self.ai_threshold < 0:
            raise ValueError("ai_threshold must be >= 0")
        if self.max_keywords <= 0:
            raise ValueError("max_keywords must be > 0")


class Aspect(Enum):
    """Business aspects for automotive analytics.

    Each aspect represents a category of customer feedback that's
    actionable for business decisions.
    """

    DESIGN = ASPECT_DESIGN
    PERFORMANCE = ASPECT_PERFORMANCE
    PRICE = ASPECT_PRICE
    SERVICE = ASPECT_SERVICE
    GENERAL = ASPECT_GENERAL

    def __str__(self) -> str:
        """String representation."""
        return self.value


@dataclass
class KeywordItem:
    """Single keyword with aspect mapping."""

    keyword: str
    aspect: str
    score: float
    source: str


@dataclass
class Metadata:
    """Extraction metadata."""

    dict_matches: int
    ai_matches: int
    total_keywords: int
    total_time_ms: float


@dataclass
class Output:
    """Output of keyword extraction.

    Attributes:
        keywords: List of extracted keywords with aspect labels
        metadata: Extraction statistics and timing info
    """

    keywords: list[KeywordItem]
    metadata: Metadata


@dataclass
class Input:
    """Input structure for keyword extraction."""

    text: str


__all__ = [
    "Config",
    "Aspect",
    "KeywordItem",
    "Metadata",
    "Output",
    "Input",
]
