# crisis/constant.py — detection thresholds

# Issue pressure thresholds
ISSUE_PRESSURE_WATCH = 5.0
ISSUE_PRESSURE_WARNING = 12.0
ISSUE_PRESSURE_CRITICAL = 25.0

# Thread controversy thresholds
CONTROVERSY_WATCH = 0.45
CONTROVERSY_WARNING = 0.65
CONTROVERSY_CRITICAL = 0.80

# Sentiment collapse: proportion of negative sentiment entities/mentions
SENTIMENT_COLLAPSE_WATCH = 0.40
SENTIMENT_COLLAPSE_WARNING = 0.60
SENTIMENT_COLLAPSE_CRITICAL = 0.75

# Severity → composite weight
SEVERITY_WEIGHT: dict[str, float] = {
    "low": 0.3,
    "medium": 1.0,
    "high": 1.8,
    "critical_like_proxy": 2.5,
}

__all__ = [
    "ISSUE_PRESSURE_WATCH",
    "ISSUE_PRESSURE_WARNING",
    "ISSUE_PRESSURE_CRITICAL",
    "CONTROVERSY_WATCH",
    "CONTROVERSY_WARNING",
    "CONTROVERSY_CRITICAL",
    "SENTIMENT_COLLAPSE_WATCH",
    "SENTIMENT_COLLAPSE_WARNING",
    "SENTIMENT_COLLAPSE_CRITICAL",
    "SEVERITY_WEIGHT",
]
