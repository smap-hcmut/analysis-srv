"""Impact Calculation use case.

This module implements the pure business-logic for computing:
- EngagementScore
- ReachScore
- Platform & sentiment multipliers
- Raw impact and normalized ImpactScore (0–100)
- Viral and KOL flags
- Risk matrix classification
"""

import math
from typing import Optional

from pkg.logger.logger import Logger
from internal.impact_calculation.interface import IImpactCalculation
from internal.impact_calculation.type import *
from internal.impact_calculation.constant import *


class ImpactCalculation(IImpactCalculation):
    """Compute ImpactScore, RiskLevel and diagnostic breakdown for a post."""

    def __init__(self, config: Config, logger: Optional[Logger] = None):
        """Initialize impact calculation use case.

        Args:
            config: Configuration for impact calculation
            logger: Logger instance (optional). If None, no logging will be performed.
        """
        self.config = config
        self.logger = logger

        if self.logger:
            self.logger.info(
                "[ImpactCalculation] Initialized",
                extra={
                    "viral_threshold": self.config.viral_threshold,
                    "kol_follower_threshold": self.config.kol_follower_threshold,
                    "max_raw_score_ceiling": self.config.max_raw_score_ceiling,
                },
            )

    def process(self, input_data: Input) -> Output:
        """Process input data and return output.

        Args:
            input_data: Input structure with interaction, author, sentiment, platform

        Returns:
            Output with impact_score, risk_level, flags, and breakdown

        Raises:
            ValueError: If input_data is invalid
            Exception: If processing fails
        """
        if not isinstance(input_data, Input):
            error_msg = "input_data must be an instance of Input"
            if self.logger:
                self.logger.error(
                    "[ImpactCalculation] Invalid input type",
                    extra={"input_type": type(input_data).__name__},
                )
            raise ValueError(error_msg)

        try:
            if self.logger:
                self.logger.debug(
                    "[ImpactCalculation] Processing started",
                    extra={
                        "platform": input_data.platform,
                        "followers": input_data.author.followers,
                        "sentiment": input_data.sentiment.label,
                    },
                )

            # Calculate engagement score
            engagement_score = self._calculate_engagement(input_data.interaction)

            # Calculate reach score
            reach_score = self._calculate_reach(input_data.author)

            # Get multipliers
            platform_multiplier = self._get_platform_multiplier(input_data.platform)
            sentiment_amplifier = self._get_sentiment_amplifier(
                input_data.sentiment.label
            )

            # Calculate raw impact
            raw_impact = (
                engagement_score
                * reach_score
                * platform_multiplier
                * sentiment_amplifier
            )

            # Normalize to 0-100
            impact_score = self._normalize_impact(raw_impact)

            # Determine flags
            is_kol = input_data.author.followers >= self.config.kol_follower_threshold
            is_viral = impact_score >= self.config.viral_threshold

            # Calculate risk level
            risk_level = self._calculate_risk(
                impact_score=impact_score,
                sentiment_label=input_data.sentiment.label,
                is_kol=is_kol,
            )

            # Build breakdown
            breakdown = ImpactBreakdown(
                engagement_score=engagement_score,
                reach_score=reach_score,
                platform_multiplier=platform_multiplier,
                sentiment_amplifier=sentiment_amplifier,
                raw_impact=raw_impact,
            )

            if self.logger:
                self.logger.info(
                    "[ImpactCalculation] Processing completed",
                    extra={
                        "impact_score": impact_score,
                        "risk_level": risk_level,
                        "is_viral": is_viral,
                        "is_kol": is_kol,
                    },
                )

            return Output(
                impact_score=impact_score,
                risk_level=risk_level,
                is_viral=is_viral,
                is_kol=is_kol,
                impact_breakdown=breakdown,
            )

        except ValueError:
            raise
        except Exception as e:
            if self.logger:
                self.logger.error(
                    "[ImpactCalculation] Processing failed",
                    extra={"error": str(e), "error_type": type(e).__name__},
                )
            raise

    def _calculate_engagement(self, interaction: InteractionInput) -> float:
        """Compute EngagementScore as a weighted sum of interactions."""
        views = max(0, interaction.views)
        likes = max(0, interaction.likes)
        comments = max(0, interaction.comments_count)
        shares = max(0, interaction.shares)
        saves = max(0, interaction.saves)

        return (
            views * self.config.weight_view
            + likes * self.config.weight_like
            + comments * self.config.weight_comment
            + saves * self.config.weight_save
            + shares * self.config.weight_share
        )

    def _calculate_reach(self, author: AuthorInput) -> float:
        """Compute ReachScore using log10(followers + 1) and verified bonus."""
        followers = max(0, author.followers)

        base = math.log10(followers + 1)
        if base <= 0:
            return 0.0

        if author.is_verified:
            base *= VERIFIED_BONUS_MULTIPLIER

        return base

    def _get_platform_multiplier(self, platform: str) -> float:
        """Map platform string to configured multiplier."""
        normalized = (platform or "").strip().upper()

        if normalized == PLATFORM_TIKTOK:
            return self.config.platform_weight_tiktok
        if normalized == PLATFORM_FACEBOOK:
            return self.config.platform_weight_facebook
        if normalized == PLATFORM_YOUTUBE:
            return self.config.platform_weight_youtube
        if normalized == PLATFORM_INSTAGRAM:
            return self.config.platform_weight_instagram

        return self.config.platform_weight_unknown

    def _get_sentiment_amplifier(self, label: str) -> float:
        """Return sentiment amplifier based on overall sentiment label."""
        normalized = (label or "").strip().upper()

        if normalized == SENTIMENT_NEGATIVE:
            return self.config.amp_negative
        if normalized == SENTIMENT_POSITIVE:
            return self.config.amp_positive

        # Default to NEUTRAL
        return self.config.amp_neutral

    def _normalize_impact(self, raw_impact: float) -> float:
        """Normalize raw impact to a 0–100 ImpactScore."""
        ceiling = max(self.config.max_raw_score_ceiling, 1.0)
        if raw_impact <= 0:
            return SCORE_MIN

        score = (raw_impact / ceiling) * SCORE_MAX
        # Saturate at 100
        return min(SCORE_MAX, score)

    def _calculate_risk(
        self, impact_score: float, sentiment_label: str, is_kol: bool
    ) -> str:
        """Classify risk level using the risk matrix from the spec."""
        label = (sentiment_label or "").strip().upper()

        high_impact = impact_score >= IMPACT_HIGH_THRESHOLD
        medium_impact = IMPACT_MEDIUM_THRESHOLD <= impact_score < IMPACT_HIGH_THRESHOLD
        high_but_not_negative = (
            impact_score >= IMPACT_HIGH_NON_NEGATIVE_THRESHOLD
            and label in {SENTIMENT_NEUTRAL, SENTIMENT_POSITIVE}
        )

        if high_impact and label == SENTIMENT_NEGATIVE and is_kol:
            return RISK_CRITICAL
        if high_impact and label == SENTIMENT_NEGATIVE and not is_kol:
            return RISK_HIGH
        if (medium_impact and label == SENTIMENT_NEGATIVE) or high_but_not_negative:
            return RISK_MEDIUM

        return RISK_LOW


__all__ = ["ImpactCalculation"]
