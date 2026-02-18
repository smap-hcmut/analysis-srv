from dataclasses import dataclass
from enum import Enum
from .constant import *


@dataclass
class Config:
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
    DESIGN = ASPECT_DESIGN
    PERFORMANCE = ASPECT_PERFORMANCE
    PRICE = ASPECT_PRICE
    SERVICE = ASPECT_SERVICE
    GENERAL = ASPECT_GENERAL

    def __str__(self) -> str:
        return self.value


@dataclass
class KeywordItem:
    keyword: str
    aspect: str
    score: float
    source: str


@dataclass
class Metadata:
    dict_matches: int
    ai_matches: int
    total_keywords: int
    total_time_ms: float


@dataclass
class Output:
    keywords: list[KeywordItem]
    metadata: Metadata


@dataclass
class Input:
    text: str


__all__ = [
    "Config",
    "Aspect",
    "KeywordItem",
    "Metadata",
    "Output",
    "Input",
]
