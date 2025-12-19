"""Example script for ImpactCalculator (Module 5).

Demonstrates how to compute Impact & Risk scores for a few realistic
Vietnamese social media scenarios (crisis, silent user, brand love).
"""

from typing import Any, Dict

from services.analytics.impact import ImpactCalculator


def pretty_print_scenario(name: str, result: Dict[str, Any]) -> None:
    print(f"\n=== {name} ===")
    print(f"Impact Score : {result['impact_score']:.2f}")
    print(f"Risk Level   : {result['risk_level']}")
    print(f"Is Viral     : {result['is_viral']}")
    print(f"Is KOL       : {result['is_kol']}")
    print("Breakdown    :", result["impact_breakdown"])


def main() -> None:
    calc = ImpactCalculator()

    # Crisis: KOL, high engagement, negative sentiment
    crisis_interaction = {
        "views": 100_000,
        "likes": 5_000,
        "comments_count": 800,
        "shares": 300,
        "saves": 150,
    }
    crisis_author = {"followers": 100_000, "is_verified": True}
    crisis_sentiment = {"label": "NEGATIVE", "score": -0.9}

    crisis_result = calc.calculate(
        crisis_interaction, crisis_author, crisis_sentiment, platform="TIKTOK"
    )
    pretty_print_scenario("Crisis (KOL, negative)", crisis_result)

    # Silent user: low engagement, negative sentiment
    silent_interaction = {
        "views": 50,
        "likes": 5,
        "comments_count": 1,
        "shares": 0,
        "saves": 0,
    }
    silent_author = {"followers": 10, "is_verified": False}
    silent_sentiment = {"label": "NEGATIVE", "score": -0.5}

    silent_result = calc.calculate(
        silent_interaction, silent_author, silent_sentiment, platform="FACEBOOK"
    )
    pretty_print_scenario("Silent user (low impact)", silent_result)

    # Brand love: viral positive campaign
    love_interaction = {
        "views": 200_000,
        "likes": 10_000,
        "comments_count": 1_500,
        "shares": 500,
        "saves": 300,
    }
    love_author = {"followers": 80_000, "is_verified": True}
    love_sentiment = {"label": "POSITIVE", "score": 0.9}

    love_result = calc.calculate(love_interaction, love_author, love_sentiment, platform="YOUTUBE")
    pretty_print_scenario("Brand love (viral positive)", love_result)


if __name__ == "__main__":
    main()
