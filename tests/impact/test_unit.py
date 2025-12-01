"""Unit tests for ImpactCalculator."""

from typing import Any, Dict

from services.analytics.impact import ImpactCalculator


def _make_calculator() -> ImpactCalculator:
    return ImpactCalculator()


class TestScenariosFromSpec:
    """Scenario-style tests aligned with module_phase_5.md."""

    def test_crisis_kol_high_engagement_negative(self) -> None:
        """KOL crisis: high engagement, negative sentiment -> high score, CRITICAL."""
        calc = _make_calculator()

        interaction: Dict[str, Any] = {
            "views": 100_000,
            "likes": 5_000,
            "comments_count": 800,
            "shares": 300,
            "saves": 150,
        }
        author: Dict[str, Any] = {"followers": 100_000, "is_verified": True}
        sentiment = {"label": "NEGATIVE", "score": -0.9}

        result = calc.calculate(interaction, author, sentiment, platform="TIKTOK")

        assert result["impact_score"] >= 80.0
        assert result["risk_level"] == "CRITICAL"
        assert result["is_viral"] is True
        assert result["is_kol"] is True

    def test_silent_user_low_engagement_negative(self) -> None:
        """Silent user: low engagement, negative sentiment -> low score, LOW risk."""
        calc = _make_calculator()

        interaction: Dict[str, Any] = {
            "views": 50,
            "likes": 5,
            "comments_count": 1,
            "shares": 0,
            "saves": 0,
        }
        author: Dict[str, Any] = {"followers": 10, "is_verified": False}
        sentiment = {"label": "NEGATIVE", "score": -0.5}

        result = calc.calculate(interaction, author, sentiment, platform="FACEBOOK")

        assert result["impact_score"] < 10.0
        assert result["risk_level"] == "LOW"
        assert result["is_viral"] is False
        assert result["is_kol"] is False

    def test_brand_love_viral_positive(self) -> None:
        """Brand love: viral positive post -> high score, non-critical risk."""
        calc = _make_calculator()

        interaction: Dict[str, Any] = {
            "views": 200_000,
            "likes": 10_000,
            "comments_count": 1_500,
            "shares": 500,
            "saves": 300,
        }
        author: Dict[str, Any] = {"followers": 80_000, "is_verified": True}
        sentiment = {"label": "POSITIVE", "score": 0.9}

        result = calc.calculate(interaction, author, sentiment, platform="YOUTUBE")

        assert result["impact_score"] >= 80.0
        # Per current risk matrix, high-impact positive is MEDIUM (viral but not crisis).
        assert result["risk_level"] in {"LOW", "MEDIUM"}
        assert result["is_viral"] is True
        assert result["is_kol"] is True


class TestEdgeCases:
    """Edge case coverage for robustness."""

    def test_zero_followers_zero_engagement(self) -> None:
        """Zero metrics should result in zero impact and LOW risk."""
        calc = _make_calculator()

        interaction: Dict[str, Any] = {
            "views": 0,
            "likes": 0,
            "comments_count": 0,
            "shares": 0,
            "saves": 0,
        }
        author: Dict[str, Any] = {"followers": 0, "is_verified": False}
        sentiment = {"label": "NEUTRAL", "score": 0.0}

        result = calc.calculate(interaction, author, sentiment, platform="UNKNOWN")

        assert result["impact_score"] == 0.0
        assert result["risk_level"] == "LOW"
        assert result["is_viral"] is False
        assert result["is_kol"] is False

    def test_missing_or_unknown_platform(self) -> None:
        """Unknown platform still produces a valid score using UNKNOWN multiplier."""
        calc = _make_calculator()

        interaction: Dict[str, Any] = {
            "views": 10_000,
            "likes": 500,
            "comments_count": 50,
            "shares": 20,
            "saves": 10,
        }
        author: Dict[str, Any] = {"followers": 5_000, "is_verified": False}
        sentiment = {"label": "NEGATIVE", "score": -0.6}

        result_unknown = calc.calculate(interaction, author, sentiment, platform="UNKNOWN")
        result_empty = calc.calculate(interaction, author, sentiment, platform="")

        assert result_unknown["impact_score"] > 0.0
        assert result_empty["impact_score"] == result_unknown["impact_score"]

    def test_neutral_sentiment_with_high_engagement(self) -> None:
        """High engagement neutral posts should have medium impact and MEDIUM/LOW risk."""
        calc = _make_calculator()

        interaction: Dict[str, Any] = {
            "views": 150_000,
            "likes": 7_000,
            "comments_count": 900,
            "shares": 250,
            "saves": 200,
        }
        author: Dict[str, Any] = {"followers": 60_000, "is_verified": False}
        sentiment = {"label": "NEUTRAL", "score": 0.0}

        result = calc.calculate(interaction, author, sentiment, platform="TIKTOK")

        assert result["impact_score"] > 0.0
        assert result["risk_level"] in {"LOW", "MEDIUM"}
