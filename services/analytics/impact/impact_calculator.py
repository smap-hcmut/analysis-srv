"""Core Impact & Risk Calculator (Module 5).

This module implements the pure business-logic for computing:
- EngagementScore
- ReachScore
- Platform & sentiment multipliers
- Raw impact and normalized ImpactScore (0–100)
- Viral and KOL flags

Risk matrix classification is implemented via `_calculate_risk` and will be
refined/validated alongside Task 3.2.
"""

from __future__ import annotations

import math
from typing import Any, Dict, Mapping

from core.config import settings


class ImpactCalculator:
    """Compute ImpactScore, RiskLevel and diagnostic breakdown for a post.

    This class is intentionally stateless and side‑effect free; it reads
    configuration from `core.config.settings` but performs no I/O.
    """

    def __init__(self) -> None:
        # Snapshot config so repeated calls are deterministic and cheap.
        self._cfg = settings

    def calculate(
        self,
        interaction: Mapping[str, Any],
        author: Mapping[str, Any],
        sentiment: Mapping[str, Any],
        platform: str,
    ) -> Dict[str, Any]:
        """Calculate impact & risk metrics for a single post.

        Parameters
        ----------
        interaction:
            Dict‑like with at least: views, likes, comments_count, shares, saves.
        author:
            Dict‑like with at least: followers, is_verified.
        sentiment:
            Overall sentiment output: {"label": "NEGATIVE|NEUTRAL|POSITIVE", "score": float}.
        platform:
            Platform identifier string: "TIKTOK" | "FACEBOOK" | "YOUTUBE" | "INSTAGRAM" | "UNKNOWN".
        """

        engagement_score = self._calculate_engagement(interaction)
        reach_score = self._calculate_reach(author)

        platform_multiplier = self._get_platform_multiplier(platform)
        sentiment_amplifier = self._get_sentiment_amplifier(sentiment.get("label"))

        raw_impact = engagement_score * reach_score * platform_multiplier * sentiment_amplifier

        impact_score = self._normalize_impact(raw_impact)

        followers = max(0, int(author.get("followers", 0) or 0))
        is_kol = followers >= int(self._cfg.impact_kol_follower_threshold)
        is_viral = impact_score >= float(self._cfg.impact_viral_threshold)

        risk_level = self._calculate_risk(
            impact_score=impact_score,
            sentiment_label=str(sentiment.get("label") or "NEUTRAL"),
            is_kol=is_kol,
        )

        return {
            "impact_score": impact_score,
            "risk_level": risk_level,
            "is_viral": is_viral,
            "is_kol": is_kol,
            "impact_breakdown": {
                "engagement_score": engagement_score,
                "reach_score": reach_score,
                "platform_multiplier": platform_multiplier,
                "sentiment_amplifier": sentiment_amplifier,
                "raw_impact": raw_impact,
            },
        }

    # ---- Private helpers -------------------------------------------------

    def _calculate_engagement(self, interaction: Mapping[str, Any]) -> float:
        """Compute EngagementScore as a weighted sum of interactions."""
        views = max(0, int(interaction.get("views", 0) or 0))
        likes = max(0, int(interaction.get("likes", 0) or 0))
        comments = max(0, int(interaction.get("comments_count", 0) or 0))
        shares = max(0, int(interaction.get("shares", 0) or 0))
        saves = max(0, int(interaction.get("saves", 0) or 0))

        return (
            views * float(self._cfg.impact_weight_view)
            + likes * float(self._cfg.impact_weight_like)
            + comments * float(self._cfg.impact_weight_comment)
            + saves * float(self._cfg.impact_weight_save)
            + shares * float(self._cfg.impact_weight_share)
        )

    def _calculate_reach(self, author: Mapping[str, Any]) -> float:
        """Compute ReachScore using log10(followers + 1) and verified bonus."""
        followers = max(0, int(author.get("followers", 0) or 0))
        is_verified = bool(author.get("is_verified", False))

        base = math.log10(followers + 1)
        if base <= 0:
            return 0.0

        if is_verified:
            base *= 1.2  # Verified bonus per design.md / module_phase_5.md
        return base

    def _get_platform_multiplier(self, platform: str) -> float:
        """Map platform string to configured multiplier."""
        normalized = (platform or "").strip().upper()

        if normalized == "TIKTOK":
            return float(self._cfg.impact_platform_weight_tiktok)
        if normalized == "FACEBOOK":
            return float(self._cfg.impact_platform_weight_facebook)
        if normalized == "YOUTUBE":
            return float(self._cfg.impact_platform_weight_youtube)
        if normalized == "INSTAGRAM":
            return float(self._cfg.impact_platform_weight_instagram)

        return float(self._cfg.impact_platform_weight_unknown)

    def _get_sentiment_amplifier(self, label: Any) -> float:
        """Return sentiment amplifier based on overall sentiment label."""
        normalized = str(label or "").strip().upper()

        if normalized == "NEGATIVE":
            return float(self._cfg.impact_amp_negative)
        if normalized == "POSITIVE":
            return float(self._cfg.impact_amp_positive)

        # Default to NEUTRAL
        return float(self._cfg.impact_amp_neutral)

    def _normalize_impact(self, raw_impact: float) -> float:
        """Normalize raw impact to a 0–100 ImpactScore."""
        ceiling = max(float(self._cfg.impact_max_raw_score_ceiling), 1.0)
        if raw_impact <= 0:
            return 0.0
        score = (raw_impact / ceiling) * 100.0
        # Saturate at 100 as per spec.
        return min(100.0, score)

    def _calculate_risk(self, impact_score: float, sentiment_label: str, is_kol: bool) -> str:
        """Classify risk level using the risk matrix from the spec.

        Note: Task 3.2 will validate and adjust thresholds if needed.
        """
        label = (sentiment_label or "").strip().upper()

        high_impact = impact_score >= 70.0
        medium_impact = 40.0 <= impact_score < 70.0
        # Slightly lower high‑impact threshold for neutral/positive per design
        high_but_not_negative = impact_score >= 60.0 and label in {"NEUTRAL", "POSITIVE"}

        if high_impact and label == "NEGATIVE" and is_kol:
            return "CRITICAL"
        if high_impact and label == "NEGATIVE" and not is_kol:
            return "HIGH"
        if (medium_impact and label == "NEGATIVE") or high_but_not_negative:
            return "MEDIUM"

        return "LOW"
