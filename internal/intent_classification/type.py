from dataclasses import dataclass, field
from enum import Enum
from .constant import *


@dataclass
class Config:
    patterns_path: str | None = DEFAULT_PATTERNS_PATH
    confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD

    def __post_init__(self):
        if not 0.0 <= self.confidence_threshold <= 1.0:
            raise ValueError("confidence_threshold must be between 0.0 and 1.0")


class Intent(Enum):
    CRISIS = PRIORITY_CRISIS
    SEEDING = PRIORITY_SEEDING
    SPAM = PRIORITY_SPAM - 1
    COMPLAINT = PRIORITY_COMPLAINT
    LEAD = PRIORITY_LEAD
    SUPPORT = PRIORITY_SUPPORT
    DISCUSSION = PRIORITY_DISCUSSION

    @property
    def priority(self) -> int:
        if self == Intent.SPAM:
            return PRIORITY_SPAM
        return self.value

    def __str__(self) -> str:
        return self.name


@dataclass
class Output:
    intent: Intent
    confidence: float
    should_skip: bool
    matched_patterns: list[str] = field(default_factory=list)


@dataclass
class Input:
    text: str


__all__ = [
    "Config",
    "Intent",
    "Output",
    "Input",
]
