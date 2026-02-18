from dataclasses import dataclass, field
from typing import Any
from .constant import *


@dataclass
class Config:
    # Interaction weights
    weight_view: float = DEFAULT_WEIGHT_VIEW
    weight_like: float = DEFAULT_WEIGHT_LIKE
    weight_comment: float = DEFAULT_WEIGHT_COMMENT
    weight_save: float = DEFAULT_WEIGHT_SAVE
    weight_share: float = DEFAULT_WEIGHT_SHARE

    # Platform multipliers
    platform_weight_tiktok: float = DEFAULT_PLATFORM_WEIGHT_TIKTOK
    platform_weight_facebook: float = DEFAULT_PLATFORM_WEIGHT_FACEBOOK
    platform_weight_youtube: float = DEFAULT_PLATFORM_WEIGHT_YOUTUBE
    platform_weight_instagram: float = DEFAULT_PLATFORM_WEIGHT_INSTAGRAM
    platform_weight_unknown: float = DEFAULT_PLATFORM_WEIGHT_UNKNOWN

    # Sentiment amplifiers
    amp_negative: float = DEFAULT_AMP_NEGATIVE
    amp_neutral: float = DEFAULT_AMP_NEUTRAL
    amp_positive: float = DEFAULT_AMP_POSITIVE

    # Thresholds
    viral_threshold: float = DEFAULT_VIRAL_THRESHOLD
    kol_follower_threshold: int = DEFAULT_KOL_FOLLOWER_THRESHOLD
    max_raw_score_ceiling: float = DEFAULT_MAX_RAW_SCORE_CEILING

    def __post_init__(self):
        if self.max_raw_score_ceiling <= 0:
            raise ValueError("max_raw_score_ceiling must be > 0")
        if not 0 <= self.viral_threshold <= 100:
            raise ValueError("viral_threshold must be between 0 and 100")
        if self.kol_follower_threshold < 0:
            raise ValueError("kol_follower_threshold must be >= 0")


@dataclass
class InteractionInput:
    views: int = 0
    likes: int = 0
    comments_count: int = 0
    shares: int = 0
    saves: int = 0


@dataclass
class AuthorInput:
    followers: int = 0
    is_verified: bool = False


@dataclass
class SentimentInput:
    label: str = SENTIMENT_NEUTRAL
    score: float = 0.0


@dataclass
class ImpactBreakdown:
    engagement_score: float
    reach_score: float
    platform_multiplier: float
    sentiment_amplifier: float
    raw_impact: float


@dataclass
class Output:
    impact_score: float
    risk_level: str
    is_viral: bool
    is_kol: bool
    impact_breakdown: ImpactBreakdown

    engagement_score: float = 0.0
    virality_score: float = 0.0
    influence_score: float = 0.0
    risk_factors: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class Input:
    interaction: InteractionInput
    author: AuthorInput
    sentiment: SentimentInput
    platform: str = PLATFORM_UNKNOWN
    text: str = ""


__all__ = [
    "Config",
    "InteractionInput",
    "AuthorInput",
    "SentimentInput",
    "ImpactBreakdown",
    "Output",
    "Input",
]
