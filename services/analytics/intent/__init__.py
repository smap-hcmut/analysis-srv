"""Intent Classification Module.

This module provides the IntentClassifier for categorizing social media posts
into 7 intent types using regex-based pattern matching.
"""

from services.analytics.intent.intent_classifier import (
    Intent,
    IntentResult,
    IntentClassifier,
)

__all__ = ["Intent", "IntentResult", "IntentClassifier"]
