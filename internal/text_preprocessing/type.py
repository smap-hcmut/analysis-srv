from dataclasses import dataclass, field
from .constant import *


@dataclass
class Config:
    min_text_length: int = DEFAULT_MIN_TEXT_LENGTH
    max_comments: int = DEFAULT_MAX_COMMENTS

    def __post_init__(self):
        if self.min_text_length < 0:
            raise ValueError("min_text_length must be >= 0")
        if self.max_comments < 0:
            raise ValueError("max_comments must be >= 0")


@dataclass
class Stats:
    total_length: int
    is_too_short: bool
    hashtag_ratio: float
    reduction_ratio: float
    has_transcription: bool
    has_phone: bool
    has_spam_keyword: bool


@dataclass
class SourceBreakdown:
    caption_len: int
    transcript_len: int
    comments_len: int


@dataclass
class Output:
    clean_text: str
    stats: Stats
    source_breakdown: SourceBreakdown

    is_spam: bool = False
    spam_reasons: list[str] = field(default_factory=list)


@dataclass
class ContentInput:
    text: str = ""
    transcription: str = ""


@dataclass
class CommentInput:
    text: str
    likes: int = 0


@dataclass
class Input:
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
