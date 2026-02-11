from dataclasses import dataclass
from typing import Optional


@dataclass
class AnalyticsResult:
    """Result of analytics processing."""

    message_id: str
    sentiment: str
    confidence: float
    keywords: list[str]
    success: bool
    error_message: Optional[str] = None


__all__ = ["AnalyticsResult"]
