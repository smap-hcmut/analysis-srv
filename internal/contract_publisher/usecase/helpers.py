"""Shared helpers for contract publisher payload builders."""

from datetime import datetime

from internal.contract_publisher.constant import (
    _ATTACHMENT_TYPE_MAP,
    _PLATFORM_UPPER_MAP,
    _PLATFORM_LOWER_MAP,
    MEDIA_TYPE_TEXT,
    PLATFORM_OTHER,
    PLATFORM_L1_MULTI,
    SUMMARY_MAX_CHARS,
)
from internal.model.uap import UAPRecord
from pkg.time_utils import utc_now_iso, datetime_to_iso


def normalize_platform_upper(source_type: str) -> str:
    """Layer 3 contract expects UPPERCASE platform: TIKTOK, FACEBOOK, etc."""
    key = (source_type or "").lower()
    return _PLATFORM_UPPER_MAP.get(key, PLATFORM_OTHER)


def normalize_platform_lower(source_type: str) -> str:
    """Layer 1 contract expects lowercase platform: tiktok, facebook, etc."""
    key = (source_type or "").lower()
    return _PLATFORM_LOWER_MAP.get(key, PLATFORM_L1_MULTI)


def detect_media_type(uap: UAPRecord) -> str:
    """Derive uap_media_type from UAPRecord.content.attachments.

    UAPContent does not have a direct media_type field.
    Falls back to "text" if no attachment found or type not recognized.
    """
    if uap.content and uap.content.attachments:
        first = uap.content.attachments[0]
        return _ATTACHMENT_TYPE_MAP.get((first.type or "").lower(), MEDIA_TYPE_TEXT)
    return MEDIA_TYPE_TEXT


def truncate_summary(text: str, max_chars: int = SUMMARY_MAX_CHARS) -> str:
    """Generate a fallback summary from clean_text when summary is empty."""
    if not text:
        return ""
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + "\u2026"


def normalize_sentiment_score(label: str, score: float) -> float:
    """Re-sign sentiment score to contract range -1.0..+1.0.

    Current model outputs 0.0..1.0. Contract requires negative values for
    NEGATIVE sentiment.
    """
    if label == "NEGATIVE" and score > 0:
        return -score
    return score


def safe_iso_utc(dt: datetime | None) -> str:
    """Convert datetime to RFC3339 UTC string. Returns empty string if None."""
    return datetime_to_iso(dt)


def now_iso_utc() -> str:
    return utc_now_iso()


def min_iso_utc(timestamps: list[str]) -> str:
    """Return the earliest RFC3339 UTC timestamp from a list. Returns now if empty."""
    valid = [t for t in timestamps if t]
    if not valid:
        return now_iso_utc()
    return sorted(valid)[0]


def max_iso_utc(timestamps: list[str]) -> str:
    """Return the latest RFC3339 UTC timestamp from a list. Returns now if empty."""
    valid = [t for t in timestamps if t]
    if not valid:
        return now_iso_utc()
    return sorted(valid)[-1]


__all__ = [
    "normalize_platform_upper",
    "normalize_platform_lower",
    "detect_media_type",
    "truncate_summary",
    "normalize_sentiment_score",
    "safe_iso_utc",
    "now_iso_utc",
    "min_iso_utc",
    "max_iso_utc",
]
