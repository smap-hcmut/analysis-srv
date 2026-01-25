"""Integration-style tests for Impact & Risk Calculator.

These tests verify that ImpactCalculator interoperates correctly with
sentiment outputs and typical pipeline-shaped data structures.
"""

from typing import Any, Dict

from services.analytics.impact import ImpactCalculator


def _make_sentiment(label: str, score: float) -> Dict[str, Any]:
    return {"label": label, "score": score}


class TestImpactWithSentimentOutput:
    """Verify compatibility with SentimentAnalyzer overall output shape."""

    def test_impact_with_negative_overall_sentiment(self) -> None:
        calc = ImpactCalculator()

        interaction: Dict[str, Any] = {
            "views": 50_000,
            "likes": 2_000,
            "comments_count": 300,
            "shares": 120,
            "saves": 80,
        }
        author: Dict[str, Any] = {"followers": 40_000, "is_verified": False}
        sentiment_overall = _make_sentiment("NEGATIVE", -0.7)

        result = calc.calculate(interaction, author, sentiment_overall, platform="FACEBOOK")

        assert "impact_score" in result
        assert "risk_level" in result
        assert "impact_breakdown" in result
        assert result["impact_breakdown"]["engagement_score"] > 0
        assert result["impact_breakdown"]["reach_score"] > 0

    def test_impact_fields_are_consistent(self) -> None:
        """Ensure consistency between breakdown and top-level flags."""
        calc = ImpactCalculator()

        interaction: Dict[str, Any] = {
            "views": 1_000,
            "likes": 100,
            "comments_count": 20,
            "shares": 5,
            "saves": 3,
        }
        author: Dict[str, Any] = {"followers": 1_000, "is_verified": False}
        sentiment_overall = _make_sentiment("NEGATIVE", -0.2)

        result = calc.calculate(interaction, author, sentiment_overall, platform="INSTAGRAM")

        breakdown = result["impact_breakdown"]

        assert (
            breakdown["raw_impact"]
            == breakdown["engagement_score"]
            * breakdown["reach_score"]
            * breakdown["platform_multiplier"]
            * breakdown["sentiment_amplifier"]
        )
