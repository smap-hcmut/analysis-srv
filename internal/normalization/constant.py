"""Normalization constants."""

# Languages the pipeline actively supports for semantic analysis
SUPPORTED_LANGUAGES: frozenset[str] = frozenset({"vi", "en", "mixed"})

# text_quality_label values
QUALITY_LABEL_NORMAL = "normal"
QUALITY_LABEL_LOW_INFO = "low_information"
QUALITY_LABEL_REACTION = "reaction_only"
QUALITY_LABEL_SPAM = "spam_like"
QUALITY_LABEL_UNSUPPORTED = "unsupported_language"
QUALITY_LABEL_NO_CONTENT = "no_semantic_content"

__all__ = [
    "SUPPORTED_LANGUAGES",
    "QUALITY_LABEL_NORMAL",
    "QUALITY_LABEL_LOW_INFO",
    "QUALITY_LABEL_REACTION",
    "QUALITY_LABEL_SPAM",
    "QUALITY_LABEL_UNSUPPORTED",
    "QUALITY_LABEL_NO_CONTENT",
]
