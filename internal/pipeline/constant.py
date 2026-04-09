# Pipeline stage name constants
STAGE_NORMALIZATION = "normalize"
STAGE_DEDUP = "dedup"
STAGE_SPAM = "spam"
STAGE_THREADS = "threads"
STAGE_ENRICHMENT = "enrichment"
STAGE_REVIEW = "review"  # Phase 4+: low-confidence fact review queue
STAGE_REPORTING = "reporting"
STAGE_CRISIS = "crisis"  # Phase 6

STAGE_ORDER = [
    STAGE_NORMALIZATION,
    STAGE_DEDUP,
    STAGE_SPAM,
    STAGE_THREADS,
    STAGE_ENRICHMENT,
    STAGE_REVIEW,
    STAGE_REPORTING,
    STAGE_CRISIS,
]

__all__ = [
    "STAGE_NORMALIZATION",
    "STAGE_DEDUP",
    "STAGE_SPAM",
    "STAGE_THREADS",
    "STAGE_ENRICHMENT",
    "STAGE_REVIEW",
    "STAGE_REPORTING",
    "STAGE_CRISIS",
    "STAGE_ORDER",
]
