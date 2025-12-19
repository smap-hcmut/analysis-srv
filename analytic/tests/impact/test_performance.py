"""Performance benchmarks for ImpactCalculator.

These tests are intentionally lightweight and focus on order-of-magnitude
checks rather than micro-optimizing absolute timings.
"""

import time

from services.analytics.impact import ImpactCalculator


def _make_calculator() -> ImpactCalculator:
    return ImpactCalculator()


def _sample_payload() -> tuple[dict, dict, dict, str]:
    interaction = {
        "views": 50_000,
        "likes": 2_000,
        "comments_count": 300,
        "shares": 120,
        "saves": 80,
    }
    author = {"followers": 40_000, "is_verified": False}
    sentiment = {"label": "NEGATIVE", "score": -0.7}
    platform = "TIKTOK"
    return interaction, author, sentiment, platform


def test_single_post_under_5ms() -> None:
    """Impact calculation for a single post should be well under 5ms."""
    calc = _make_calculator()
    interaction, author, sentiment, platform = _sample_payload()

    # Warm-up
    calc.calculate(interaction, author, sentiment, platform)

    start = time.perf_counter()
    for _ in range(50):
        calc.calculate(interaction, author, sentiment, platform)
    elapsed = time.perf_counter() - start

    avg_ms = (elapsed / 50) * 1000.0

    # Allow some headroom for CI noise, but keep close to the 5ms target.
    assert avg_ms < 5.0


def test_batch_100_posts_under_100ms() -> None:
    """Batch processing 100 posts should complete under 100ms."""
    calc = _make_calculator()
    interaction, author, sentiment, platform = _sample_payload()

    # Warm-up
    calc.calculate(interaction, author, sentiment, platform)

    start = time.perf_counter()
    for _ in range(100):
        calc.calculate(interaction, author, sentiment, platform)
    elapsed = time.perf_counter() - start

    total_ms = elapsed * 1000.0

    assert total_ms < 100.0
