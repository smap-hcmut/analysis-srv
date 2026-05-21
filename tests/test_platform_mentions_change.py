from __future__ import annotations

from internal.http.analytics_service import is_reliable_platform_mentions_change


def test_platform_mentions_change_is_unreliable_for_tiny_positive_baseline():
    assert is_reliable_platform_mentions_change(2076, 1) is False


def test_platform_mentions_change_is_reliable_for_established_baseline():
    assert is_reliable_platform_mentions_change(1026, 595) is True
    assert is_reliable_platform_mentions_change(395, 298) is True


def test_platform_mentions_change_keeps_zero_and_declining_low_volume_cases_stable():
    assert is_reliable_platform_mentions_change(0, 0) is True
    assert is_reliable_platform_mentions_change(0, 1) is True
