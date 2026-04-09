"""Enum normalization utilities shared across pipeline stages.

Port from core-analysis/src/smap/run_manifest.py (platform maps)
and internal contract_publisher helpers — single source of truth.
"""

from internal.runtime.constant import (
    PLATFORM_UPSTREAM_MAP,
    PLATFORM_DIGEST_MAP,
    SENTIMENT_LABELS,
)


def normalize_platform_for_layer3(raw: str) -> str:
    """Layer 3 (batch_completed / insight cards): UPPERCASE platform."""
    return PLATFORM_UPSTREAM_MAP.get(raw.lower(), raw.upper())


def normalize_platform_for_layer1(raw: str) -> str:
    """Layer 1 (report_digest): lowercase platform."""
    return PLATFORM_DIGEST_MAP.get(raw.upper(), raw.lower())


def normalize_sentiment_label(raw: str) -> str:
    """Normalize arbitrary sentiment strings to canonical UPPERCASE label."""
    norm = raw.strip().upper()
    if norm == "POS":
        return "POSITIVE"
    if norm == "NEG":
        return "NEGATIVE"
    if norm == "NEU":
        return "NEUTRAL"
    return norm if norm in SENTIMENT_LABELS else "NEUTRAL"


__all__ = [
    "normalize_platform_for_layer3",
    "normalize_platform_for_layer1",
    "normalize_sentiment_label",
]
