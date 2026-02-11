from dataclasses import dataclass, field
from .constant import *


@dataclass
class Config:
    """Configuration for text preprocessing."""

    min_text_length: int = DEFAULT_MIN_TEXT_LENGTH
    max_comments: int = DEFAULT_MAX_COMMENTS

    def __post_init__(self):
        if self.min_text_length < 0:
            raise ValueError("min_text_length must be >= 0")
        if self.max_comments < 0:
            raise ValueError("max_comments must be >= 0")


@dataclass
class Stats:
    """Statistics from text preprocessing."""

    total_length: int
    is_too_short: bool
    hashtag_ratio: float
    reduction_ratio: float
    has_transcription: bool
    has_phone: bool
    has_spam_keyword: bool


@dataclass
class SourceBreakdown:
    """Source length breakdown."""

    caption_len: int
    transcript_len: int
    comments_len: int


@dataclass
class Output:
    """Output of text preprocessing."""

    clean_text: str
    stats: Stats
    source_breakdown: SourceBreakdown


@dataclass
class ContentInput:
    """Content input structure."""

    text: str = ""
    transcription: str = ""


@dataclass
class CommentInput:
    """Comment input structure."""

    text: str
    likes: int = 0


@dataclass
class Input:
    """Input structure for text preprocessing."""

    content: ContentInput
    comments: list[CommentInput] = field(default_factory=list)


__all__ = [
    "Config",
    "Stats",
    "SourceBreakdown",
    "Output",
    "Input",
    "ContentInput",
    "CommentInput",
]
