from dataclasses import dataclass, field
from enum import Enum
from .constant import *


@dataclass
class Config:
    """Configuration for intent classification."""

    patterns_path: str | None = DEFAULT_PATTERNS_PATH
    confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD

    def __post_init__(self):
        if not 0.0 <= self.confidence_threshold <= 1.0:
            raise ValueError("confidence_threshold must be between 0.0 and 1.0")


class Intent(Enum):
    """Intent categories for social media posts.

    Each intent has an associated priority for conflict resolution.
    Higher priority wins when multiple patterns match.
    """

    CRISIS = PRIORITY_CRISIS
    SEEDING = PRIORITY_SEEDING
    SPAM = PRIORITY_SPAM - 1  # Enum values must be unique
    COMPLAINT = PRIORITY_COMPLAINT
    LEAD = PRIORITY_LEAD
    SUPPORT = PRIORITY_SUPPORT
    DISCUSSION = PRIORITY_DISCUSSION

    @property
    def priority(self) -> int:
        """Get priority value for this intent.

        SEEDING and SPAM have equal priority for conflict resolution.
        """
        if self == Intent.SPAM:
            return PRIORITY_SPAM
        return self.value

    def __str__(self) -> str:
        """String representation of intent."""
        return self.name


@dataclass
class Output:
    """Output of intent classification.

    Attributes:
        intent: The classified intent category
        confidence: Confidence score (0.0-1.0)
        should_skip: Whether to skip AI processing for this post
        matched_patterns: List of matched pattern descriptions for debugging
    """

    intent: Intent
    confidence: float
    should_skip: bool
    matched_patterns: list[str] = field(default_factory=list)


@dataclass
class Input:
    """Input structure for intent classification."""

    text: str


__all__ = [
    "Config",
    "Intent",
    "Output",
    "Input",
]
