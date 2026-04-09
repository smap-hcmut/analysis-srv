from ..constant import (
    PRIORITY_HIGH_THRESHOLD,
    PRIORITY_MEDIUM_THRESHOLD,
    CONFIDENCE_HIGH_THRESHOLD,
    CONFIDENCE_MEDIUM_THRESHOLD,
)
from pkg.time_utils import utc_now_iso


def build_snippet(text: str, max_length: int) -> str:
    if not text:
        return ""
    if len(text) <= max_length:
        return text
    return text[:max_length].rstrip() + "..."


def confidence_label(score: float) -> str:
    if score >= CONFIDENCE_HIGH_THRESHOLD:
        return "HIGH"
    if score >= CONFIDENCE_MEDIUM_THRESHOLD:
        return "MEDIUM"
    return "LOW"


def determine_priority(impact_score: float) -> str:
    if impact_score >= PRIORITY_HIGH_THRESHOLD:
        return "HIGH"
    if impact_score >= PRIORITY_MEDIUM_THRESHOLD:
        return "MEDIUM"
    return "LOW"


def safe_iso_now() -> str:
    return utc_now_iso()
