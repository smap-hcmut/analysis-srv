# Runtime module constants

MANIFEST_VERSION = "2026.04.09-analysis-srv-r1"

SENTIMENT_LABELS = frozenset({"POSITIVE", "NEGATIVE", "NEUTRAL", "MIXED"})

# Platform normalization maps
PLATFORM_UPSTREAM_MAP: dict[str, str] = {
    "tiktok": "TIKTOK",
    "facebook": "FACEBOOK",
    "instagram": "INSTAGRAM",
    "youtube": "YOUTUBE",
}
PLATFORM_DIGEST_MAP: dict[str, str] = {v: k for k, v in PLATFORM_UPSTREAM_MAP.items()}

__all__ = [
    "MANIFEST_VERSION",
    "SENTIMENT_LABELS",
    "PLATFORM_UPSTREAM_MAP",
    "PLATFORM_DIGEST_MAP",
]
