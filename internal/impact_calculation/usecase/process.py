from pkg.logger.logger import Logger
from internal.impact_calculation.type import Input, Output, Config, ImpactBreakdown
from .helpers import (
    calculate_engagement_score,
    calculate_virality_score,
    calculate_influence_score,
    calculate_reach,
    get_platform_multiplier,
    get_sentiment_amplifier,
    normalize_impact,
    calculate_risk,
)


def process(
    input_data: Input,
    config: Config,
    logger: Logger,
) -> Output:
    try:
        logger.debug(
            "internal.impact_calculation.usecase.process: Processing started",
            extra={
                "platform": input_data.platform,
                "followers": input_data.author.followers,
                "sentiment": input_data.sentiment.label,
            },
        )

        # Engagement Score
        engagement_score = calculate_engagement_score(
            likes=input_data.interaction.likes,
            comments=input_data.interaction.comments_count,
            shares=input_data.interaction.shares,
            views=input_data.interaction.views,
        )

        # Virality Score
        virality_score = calculate_virality_score(
            likes=input_data.interaction.likes,
            comments=input_data.interaction.comments_count,
            shares=input_data.interaction.shares,
        )

        # Influence Score
        influence_score = calculate_influence_score(
            followers=input_data.author.followers, engagement_score=engagement_score
        )

        # Reach Score
        reach_score = calculate_reach(input_data.author)

        # Platform Multiplier
        platform_multiplier = get_platform_multiplier(input_data.platform, config)
        sentiment_amplifier = get_sentiment_amplifier(
            input_data.sentiment.label, config
        )

        # Raw Impact
        raw_impact = (
            engagement_score * reach_score * platform_multiplier * sentiment_amplifier
        )

        # Impact Score
        impact_score = normalize_impact(raw_impact, config)

        # Is Kol
        is_kol = input_data.author.followers >= config.kol_follower_threshold
        is_viral = impact_score >= config.viral_threshold

        # Text
        text = getattr(input_data, "text", "") or ""

        # Risk Level, Risk Score, Risk Factors
        risk_level, _, risk_factors = calculate_risk(
            impact_score=impact_score,
            sentiment_label=input_data.sentiment.label,
            sentiment_score=input_data.sentiment.score,
            text=text,
            virality_score=virality_score,
        )

        # Impact Breakdown
        breakdown = ImpactBreakdown(
            engagement_score=engagement_score,
            reach_score=reach_score,
            platform_multiplier=platform_multiplier,
            sentiment_amplifier=sentiment_amplifier,
            raw_impact=raw_impact,
        )

        logger.info(
            "internal.impact_calculation.usecase.process: Processing completed",
            extra={
                "impact_score": impact_score,
                "risk_level": risk_level,
                "is_viral": is_viral,
                "is_kol": is_kol,
                "engagement_score": engagement_score,
                "virality_score": virality_score,
                "influence_score": influence_score,
            },
        )

        return Output(
            impact_score=impact_score,
            risk_level=risk_level,
            is_viral=is_viral,
            is_kol=is_kol,
            impact_breakdown=breakdown,
            engagement_score=engagement_score,
            virality_score=virality_score,
            influence_score=influence_score,
            risk_factors=risk_factors,
        )

    except Exception as e:
        logger.error(
            "internal.impact_calculation.usecase.process: Processing failed",
            extra={"error": str(e), "error_type": type(e).__name__},
        )
        raise
