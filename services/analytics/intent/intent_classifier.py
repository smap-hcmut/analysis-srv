"""Intent Classifier for Vietnamese social media posts.

This module implements rule-based intent classification using regex patterns
to categorize posts into 7 intent types: CRISIS, SEEDING, SPAM, COMPLAINT,
LEAD, SUPPORT, and DISCUSSION.

The classifier serves as a gatekeeper in the AI processing pipeline to:
1. Filter noise early (SPAM/SEEDING) before expensive AI models
2. Prioritize crisis posts for immediate attention
3. Enrich analytics with business intelligence labels
"""

import re
import yaml
from pathlib import Path
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Pattern, Any

from core.config import settings


class Intent(Enum):
    """Intent categories for social media posts.

    Each intent has an associated priority for conflict resolution.
    Higher priority wins when multiple patterns match.

    Note: Enum values must be unique, so SEEDING=9 and SPAM=8 instead of both 9.
    Priority logic uses the priority() property instead of raw values.
    """

    CRISIS = 10  # Khủng hoảng (tẩy chay, lừa đảo, scam) - Alert + Process
    SEEDING = 9  # Spam marketing (phone numbers, sales) - SKIP
    SPAM = 8  # Garbage (vay tiền, bán sim) - SKIP
    COMPLAINT = 7  # Phàn nàn sản phẩm/dịch vụ - Flag + Process
    LEAD = 5  # Sales opportunity (hỏi giá, mua xe) - Flag + Process
    SUPPORT = 4  # Technical support needed - Flag + Process
    DISCUSSION = 1  # Normal discussion (default) - Process

    @property
    def priority(self) -> int:
        """Get priority value for this intent.

        SEEDING and SPAM have equal priority (9) for conflict resolution,
        but different enum values to remain distinct.
        """
        # Give SPAM the same priority as SEEDING for conflict resolution
        if self == Intent.SPAM:
            return 9
        return self.value

    def __str__(self) -> str:
        """String representation of intent."""
        return self.name


@dataclass
class IntentResult:
    """Result of intent classification.

    Attributes:
        intent: The classified intent category
        confidence: Confidence score (0.0-1.0)
        should_skip: Whether to skip AI processing for this post
        matched_patterns: List of matched pattern descriptions for debugging
    """

    intent: Intent
    confidence: float
    should_skip: bool
    matched_patterns: List[str]


def _compile_pattern_list(patterns: List[str]) -> List[Pattern]:
    """Helper function to compile a list of regex patterns.

    Args:
        patterns: List of regex pattern strings

    Returns:
        List of compiled Pattern objects
    """
    return [re.compile(pat, re.IGNORECASE) for pat in patterns]


class IntentClassifier:
    """Rule-based intent classifier for Vietnamese social media posts.

    Uses pre-compiled regex patterns to classify posts into 7 intent categories.
    Optimized for Vietnamese language patterns commonly found on social media.

    Example:
        >>> classifier = IntentClassifier()
        >>> result = classifier.predict("VinFast lừa đảo khách hàng")
        >>> print(result.intent)
        Intent.CRISIS
        >>> print(result.should_skip)
        False
    """

    def __init__(self):
        """Initialize classifier with pre-compiled regex patterns."""
        self.patterns: Dict[Intent, List[Pattern]] = {}
        self._compile_patterns()

    def _compile_patterns(self) -> None:
        """Compile all regex patterns for performance.

        Patterns are compiled with re.IGNORECASE for case-insensitive matching.
        Vietnamese patterns are optimized for social media text.
        """
        # Try to load patterns from external config
        patterns_dict = self._load_patterns_from_config()

        # If config loading failed or returned empty, use defaults
        if not patterns_dict:
            patterns_dict = self._get_default_patterns()

        # Compile all patterns using helper function
        self.patterns = {
            intent: _compile_pattern_list(pattern_strs)
            for intent, pattern_strs in patterns_dict.items()
        }

    def _load_patterns_from_config(self) -> Optional[Dict[Intent, List[str]]]:
        """Load patterns from external YAML configuration file."""
        try:
            config_path = Path(settings.intent_patterns_path)
            if not config_path.exists():
                return None

            with open(config_path, "r", encoding="utf-8") as f:
                config_data = yaml.safe_load(f)

            if not config_data:
                return None

            # Convert string keys to Intent enum
            patterns_dict = {}
            for intent_name, patterns in config_data.items():
                try:
                    intent = Intent[intent_name.upper()]
                    patterns_dict[intent] = patterns
                except KeyError:
                    continue  # Skip invalid intents

            return patterns_dict
        except Exception:
            # Log error in production, but here just return None to fallback
            return None

    def _get_default_patterns(self) -> Dict[Intent, List[str]]:
        """Get default hardcoded patterns as fallback."""
        return {
            Intent.CRISIS: [
                r"tẩy\s*chay",
                r"lừa\s*đảo",
                r"lừa.*đảo",
                r"scam",
                r"phốt",
                r"bóc\s*phốt",
                r"bóc.*phốt",
                r"lừa\s*gạt",
                r"gian\s*lận",
                r"cảnh\s*báo",
            ],
            Intent.SEEDING: [
                r"\b0\d{9,10}\b",  # Vietnamese phone numbers
                r"zalo.*\d{9,10}",
                r"inbox.*giá",
                r"inbox.*mua",
                r"liên\s*hệ.*mua",
                r"liên\s*hệ.*\d{9}",
                r"inbox.*shop",
                r"chat.*shop",
            ],
            Intent.SPAM: [
                r"vay\s*tiền",
                r"vay\s*vốn",
                r"bán\s*sim",
                r"lãi\s*suất",
                r"giải\s*ngân",
                r"tuyển\s*dụng",
                r"cần\s*gấp",
                r"thu\s*nhập",
            ],
            Intent.COMPLAINT: [
                r"lỗi.*(không|chưa).*sửa",
                r"lỗi.*chưa.*khắc\s*phục",
                r"thất\s*vọng",
                r"tệ\s*quá",
                r"tệ.*nhất",
                r"đừng.*mua",
                r"không.*nên.*mua",
                r"rác.*quá",
                r"(tồi|tệ|kém).*chất\s*lượng",
                r"chất\s*lượng.*(tệ|kém)",
            ],
            Intent.LEAD: [
                r"giá.*bao\s*nhiêu",
                r"bao\s*nhiêu.*tiền",
                r"mua.*ở\s*đâu",
                r"ở\s*đâu.*mua",
                r"test\s*drive",
                r"xin.*giá",
                r"cho.*xin.*giá",
                r"đặt.*mua",
                r"đặt.*cọc",
                r"mua.*ngay",
            ],
            Intent.SUPPORT: [
                r"cách.*sạc",
                r"làm\s*sao.*sạc",
                r"showroom",
                r"đại\s*lý",
                r"bảo\s*hành",
                r"sửa\s*chữa",
                r"hướng\s*dẫn",
                r"cách.*sử\s*dụng",
                r"trung\s*tâm.*bảo\s*hành",
            ],
        }

    def predict(self, text: str) -> IntentResult:
        """Classify intent of the given text.

        Uses regex pattern matching with priority-based conflict resolution.
        CRISIS > SEEDING = SPAM > COMPLAINT > LEAD > SUPPORT > DISCUSSION

        Args:
            text: Input text to classify (cleaned/preprocessed recommended)

        Returns:
            IntentResult with classification details

        Example:
            >>> classifier = IntentClassifier()
            >>> result = classifier.predict("Giá xe bao nhiêu shop?")
            >>> result.intent
            Intent.LEAD
            >>> result.confidence
            0.9
        """
        # Handle empty/None input
        if not text:
            return IntentResult(
                intent=Intent.DISCUSSION, confidence=1.0, should_skip=False, matched_patterns=[]
            )

        # Track matches: {intent: [matched_pattern_strings]}
        matches: Dict[Intent, List[str]] = {}

        # Check all patterns against text
        for intent, patterns in self.patterns.items():
            matched = []
            for pattern in patterns:
                if pattern.search(text):
                    matched.append(pattern.pattern)

            if matched:
                matches[intent] = matched

        # If no patterns matched, default to DISCUSSION
        if not matches:
            return IntentResult(
                intent=Intent.DISCUSSION, confidence=1.0, should_skip=False, matched_patterns=[]
            )

        # Resolve conflicts by priority (highest priority wins)
        # If tied priority, take the first one in the matches dict
        best_intent = max(matches.keys(), key=lambda i: i.priority)
        matched_patterns = matches[best_intent]

        # Calculate confidence based on number of matches
        # More matches = higher confidence (capped at 1.0)
        num_matches = len(matched_patterns)
        confidence = min(0.5 + (num_matches * 0.1), 1.0)

        # Determine if we should skip AI processing
        # SPAM and SEEDING should be skipped
        should_skip = best_intent in (Intent.SPAM, Intent.SEEDING)

        return IntentResult(
            intent=best_intent,
            confidence=confidence,
            should_skip=should_skip,
            matched_patterns=matched_patterns,
        )
