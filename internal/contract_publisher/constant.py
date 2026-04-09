# Kafka topics — per contract.md v1.2
# These 3 topics are consumed by knowledge-srv.
# DO NOT use "smap.analytics.output" — legacy topic, no consumer.

TOPIC_BATCH_COMPLETED = "analytics.batch.completed"
TOPIC_INSIGHTS_PUBLISHED = "analytics.insights.published"
TOPIC_REPORT_DIGEST = "analytics.report.digest"

# Batch defaults
DEFAULT_BATCH_SIZE = 100
DEFAULT_FLUSH_INTERVAL_SECONDS = 30.0

# Document gate: minimum clean_text length to be rag-indexable
RAG_MIN_TEXT_LENGTH = 50

# Summary fallback truncation length
SUMMARY_MAX_CHARS = 120

# Valid uap_media_type values (contract Section 2)
MEDIA_TYPE_VIDEO = "video"
MEDIA_TYPE_IMAGE = "image"
MEDIA_TYPE_CAROUSEL = "carousel"
MEDIA_TYPE_TEXT = "text"
MEDIA_TYPE_LIVE = "live"
MEDIA_TYPE_OTHER = "other"

# Attachment type → uap_media_type mapping
_ATTACHMENT_TYPE_MAP: dict[str, str] = {
    "video": MEDIA_TYPE_VIDEO,
    "image": MEDIA_TYPE_IMAGE,
    "carousel": MEDIA_TYPE_CAROUSEL,
    "live": MEDIA_TYPE_LIVE,
}

# Valid platform values in Layer 3 (UPPERCASE) and Layer 1 (lowercase)
PLATFORM_TIKTOK = "TIKTOK"
PLATFORM_FACEBOOK = "FACEBOOK"
PLATFORM_INSTAGRAM = "INSTAGRAM"
PLATFORM_YOUTUBE = "YOUTUBE"
PLATFORM_OTHER = "OTHER"

# Layer 1 platform values (lowercase)
PLATFORM_L1_TIKTOK = "tiktok"
PLATFORM_L1_FACEBOOK = "facebook"
PLATFORM_L1_INSTAGRAM = "instagram"
PLATFORM_L1_YOUTUBE = "youtube"
PLATFORM_L1_MULTI = "multi"
PLATFORM_L1_OTHER = "multi"  # fallback

_PLATFORM_UPPER_MAP: dict[str, str] = {
    "tiktok": PLATFORM_TIKTOK,
    "facebook": PLATFORM_FACEBOOK,
    "instagram": PLATFORM_INSTAGRAM,
    "youtube": PLATFORM_YOUTUBE,
}

_PLATFORM_LOWER_MAP: dict[str, str] = {
    "tiktok": PLATFORM_L1_TIKTOK,
    "facebook": PLATFORM_L1_FACEBOOK,
    "instagram": PLATFORM_L1_INSTAGRAM,
    "youtube": PLATFORM_L1_YOUTUBE,
}

__all__ = [
    "TOPIC_BATCH_COMPLETED",
    "TOPIC_INSIGHTS_PUBLISHED",
    "TOPIC_REPORT_DIGEST",
    "DEFAULT_BATCH_SIZE",
    "DEFAULT_FLUSH_INTERVAL_SECONDS",
    "RAG_MIN_TEXT_LENGTH",
    "SUMMARY_MAX_CHARS",
    "MEDIA_TYPE_VIDEO",
    "MEDIA_TYPE_IMAGE",
    "MEDIA_TYPE_CAROUSEL",
    "MEDIA_TYPE_TEXT",
    "MEDIA_TYPE_LIVE",
    "MEDIA_TYPE_OTHER",
    "_ATTACHMENT_TYPE_MAP",
    "_PLATFORM_UPPER_MAP",
    "_PLATFORM_LOWER_MAP",
]
