import math
from typing import Any

from internal.impact_calculation.constant import (
    ENGAGEMENT_WEIGHT_LIKE,
    ENGAGEMENT_WEIGHT_COMMENT,
    ENGAGEMENT_WEIGHT_SHARE,
    ENGAGEMENT_MIN_VIEWS_FOR_NORMALIZATION,
    ENGAGEMENT_SCORE_CAP,
    VIRALITY_DENOMINATOR_OFFSET,
    INFLUENCE_FOLLOWER_DIVISOR,
    VERIFIED_BONUS_MULTIPLIER,
    PLATFORM_TIKTOK,
    PLATFORM_FACEBOOK,
    PLATFORM_YOUTUBE,
    PLATFORM_INSTAGRAM,
    SENTIMENT_NEGATIVE,
    SENTIMENT_POSITIVE,
    SCORE_MIN,
    SCORE_MAX,
    RISK_SENTIMENT_NEGATIVE_THRESHOLD,
    RISK_SENTIMENT_BASE_WEIGHT,
    RISK_FACTOR_NEGATIVE_SENTIMENT,
    RISK_SENTIMENT_EXTREME_THRESHOLD,
    RISK_SENTIMENT_EXTREME_WEIGHT,
    RISK_FACTOR_EXTREME_NEGATIVE,
    CRISIS_KEYWORDS,
    RISK_KEYWORD_WEIGHT,
    RISK_FACTOR_KEYWORD_MATCH,
    RISK_VIRALITY_AMPLIFIER_MIN_BASE,
    RISK_VIRALITY_AMPLIFIER_THRESHOLD,
    RISK_FACTOR_VIRAL_SPREAD,
    RISK_SCORE_CRITICAL_THRESHOLD,
    RISK_CRITICAL,
    RISK_SCORE_HIGH_THRESHOLD,
    RISK_HIGH,
    RISK_SCORE_MEDIUM_THRESHOLD,
    RISK_MEDIUM,
    RISK_LOW,
)
from internal.impact_calculation.type import Config, AuthorInput


def calculate_engagement_score(
    likes: int, comments: int, shares: int, views: int
) -> float:
    likes = max(0, likes)
    comments = max(0, comments)
    shares = max(0, shares)
    views = max(0, views)

    weighted_sum = (
        likes * ENGAGEMENT_WEIGHT_LIKE
        + comments * ENGAGEMENT_WEIGHT_COMMENT
        + shares * ENGAGEMENT_WEIGHT_SHARE
    )

    if views >= ENGAGEMENT_MIN_VIEWS_FOR_NORMALIZATION:
        score = (weighted_sum / views) * 100
    else:
        # Low volume — use raw score
        score = weighted_sum

    return min(score, ENGAGEMENT_SCORE_CAP)


def calculate_virality_score(likes: int, comments: int, shares: int) -> float:
    likes = max(0, likes)
    comments = max(0, comments)
    shares = max(0, shares)

    denominator = likes + comments + VIRALITY_DENOMINATOR_OFFSET
    return shares / denominator


def calculate_influence_score(followers: int, engagement_score: float) -> float:
    followers = max(0, followers)
    normalized_followers = followers / INFLUENCE_FOLLOWER_DIVISOR
    return normalized_followers * engagement_score


def calculate_reach(author: AuthorInput) -> float:
    followers = max(0, author.followers)

    base = math.log10(followers + 1)
    if base <= 0:
        return 0.0

    if author.is_verified:
        base *= VERIFIED_BONUS_MULTIPLIER

    return base


def get_platform_multiplier(platform: str, config: Config) -> float:
    normalized = (platform or "").strip().upper()

    if normalized == PLATFORM_TIKTOK:
        return config.platform_weight_tiktok
    if normalized == PLATFORM_FACEBOOK:
        return config.platform_weight_facebook
    if normalized == PLATFORM_YOUTUBE:
        return config.platform_weight_youtube
    if normalized == PLATFORM_INSTAGRAM:
        return config.platform_weight_instagram

    return config.platform_weight_unknown


def get_sentiment_amplifier(label: str, config: Config) -> float:
    normalized = (label or "").strip().upper()

    if normalized == SENTIMENT_NEGATIVE:
        return config.amp_negative
    if normalized == SENTIMENT_POSITIVE:
        return config.amp_positive

    # Default to NEUTRAL
    return config.amp_neutral


def normalize_impact(raw_impact: float, config: Config) -> float:
    ceiling = max(config.max_raw_score_ceiling, 1.0)
    if raw_impact <= 0:
        return SCORE_MIN

    score = (raw_impact / ceiling) * SCORE_MAX
    # Saturate at 100
    return min(SCORE_MAX, score)


def calculate_risk(
    impact_score: float,
    sentiment_label: str,
    sentiment_score: float,
    text: str,
    virality_score: float,
) -> tuple[str, float, list[dict[str, Any]]]:
    risk_score = 0.0
    risk_factors = []

    # Sentiment Impact
    if sentiment_score < RISK_SENTIMENT_NEGATIVE_THRESHOLD:
        risk_score += RISK_SENTIMENT_BASE_WEIGHT
        risk_factors.append(
            {
                "factor": RISK_FACTOR_NEGATIVE_SENTIMENT,
                "severity": "MEDIUM",
                "description": f"Negative sentiment detected (score: {sentiment_score:.2f})",
            }
        )

    if sentiment_score < RISK_SENTIMENT_EXTREME_THRESHOLD:
        risk_score += RISK_SENTIMENT_EXTREME_WEIGHT
        risk_factors.append(
            {
                "factor": RISK_FACTOR_EXTREME_NEGATIVE,
                "severity": "HIGH",
                "description": f"Extreme negative sentiment (score: {sentiment_score:.2f})",
            }
        )

    # Crisis Keywords
    text_lower = text.lower() if text else ""
    matched_keywords = []
    for keyword in CRISIS_KEYWORDS:
        if keyword in text_lower:
            matched_keywords.append(keyword)

    if matched_keywords:
        risk_score += RISK_KEYWORD_WEIGHT
        risk_factors.append(
            {
                "factor": RISK_FACTOR_KEYWORD_MATCH,
                "severity": "HIGH",
                "description": f"Crisis keywords detected: {', '.join(matched_keywords)}",
            }
        )

    # Virality Amplifier
    if (
        risk_score >= RISK_VIRALITY_AMPLIFIER_MIN_BASE
        and virality_score > RISK_VIRALITY_AMPLIFIER_THRESHOLD
    ):
        amplifier = 1 + virality_score
        risk_score *= amplifier
        risk_factors.append(
            {
                "factor": RISK_FACTOR_VIRAL_SPREAD,
                "severity": "CRITICAL",
                "description": f"High virality amplifying risk (virality: {virality_score:.2f}, amplifier: {amplifier:.2f}x)",
            }
        )

    # Risk Level
    if risk_score >= RISK_SCORE_CRITICAL_THRESHOLD:
        return RISK_CRITICAL, risk_score, risk_factors
    if risk_score >= RISK_SCORE_HIGH_THRESHOLD:
        return RISK_HIGH, risk_score, risk_factors
    if risk_score >= RISK_SCORE_MEDIUM_THRESHOLD:
        return RISK_MEDIUM, risk_score, risk_factors

    return RISK_LOW, risk_score, risk_factors
