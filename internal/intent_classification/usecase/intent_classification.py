"""Intent Classification use case.

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
from typing import Optional, Pattern
from re import Pattern as RePattern

from pkg.logger.logger import Logger
from internal.intent_classification.interface import IIntentClassification
from internal.intent_classification.type import *
from internal.intent_classification.constant import *


class IntentClassification(IIntentClassification):
    """Rule-based intent classifier for Vietnamese social media posts."""

    def __init__(self, config: Config, logger: Optional[Logger] = None):
        """Initialize intent classification use case.

        Args:
            config: Configuration for intent classification
            logger: Logger instance (optional). If None, no logging will be performed.
        """
        self.config = config
        self.logger = logger
        self.patterns: dict[Intent, list[RePattern]] = {}
        self._compile_patterns()

        if self.logger:
            self.logger.info(
                "[IntentClassification] Initialized",
                extra={
                    "patterns_path": self.config.patterns_path,
                    "confidence_threshold": self.config.confidence_threshold,
                    "patterns_loaded": len(self.patterns),
                },
            )

    def _compile_patterns(self) -> None:
        """Compile all regex patterns for performance.

        Patterns are compiled with re.IGNORECASE for case-insensitive matching.
        Vietnamese patterns are optimized for social media text.
        """
        try:
            # Try to load patterns from external config
            patterns_dict = self._load_patterns_from_config()

            # If config loading failed or returned empty, use defaults
            if not patterns_dict:
                patterns_dict = self._get_default_patterns()
                if self.logger:
                    self.logger.info(
                        "[IntentClassification] Using default patterns",
                        extra={"reason": "config_not_found_or_empty"},
                    )

            # Compile all patterns
            self.patterns = {
                intent: [re.compile(pat, re.IGNORECASE) for pat in pattern_strs]
                for intent, pattern_strs in patterns_dict.items()
            }

            if self.logger:
                pattern_counts = {
                    intent.name: len(patterns)
                    for intent, patterns in self.patterns.items()
                }
                self.logger.info(
                    "[IntentClassification] Patterns compiled",
                    extra={"pattern_counts": pattern_counts},
                )

        except Exception as e:
            if self.logger:
                self.logger.error(
                    "[IntentClassification] Pattern compilation failed",
                    extra={"error": str(e), "error_type": type(e).__name__},
                )
            raise

    def _load_patterns_from_config(self) -> dict[Intent, list[str]] | None:
        """Load patterns from external YAML configuration file."""
        if not self.config.patterns_path:
            return None

        try:
            config_path = Path(self.config.patterns_path)
            if not config_path.exists():
                if self.logger:
                    self.logger.warn(
                        "[IntentClassification] Patterns file not found",
                        extra={"path": str(config_path)},
                    )
                return None

            with open(config_path, "r", encoding=FILE_ENCODING_UTF8) as f:
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
                    if self.logger:
                        self.logger.warn(
                            "[IntentClassification] Invalid intent in config",
                            extra={"intent_name": intent_name},
                        )
                    continue

            if self.logger:
                self.logger.info(
                    "[IntentClassification] Patterns loaded from config",
                    extra={
                        "path": str(config_path),
                        "intents_loaded": len(patterns_dict),
                    },
                )

            return patterns_dict

        except Exception as e:
            if self.logger:
                self.logger.error(
                    "[IntentClassification] Failed to load patterns from config",
                    extra={"error": str(e), "path": self.config.patterns_path},
                )
            return None

    def _get_default_patterns(self) -> dict[Intent, list[str]]:
        """Get default hardcoded patterns as fallback."""
        return {
            Intent.CRISIS: DEFAULT_CRISIS_PATTERNS,
            Intent.SEEDING: DEFAULT_SEEDING_PATTERNS,
            Intent.SPAM: DEFAULT_SPAM_PATTERNS,
            Intent.COMPLAINT: DEFAULT_COMPLAINT_PATTERNS,
            Intent.LEAD: DEFAULT_LEAD_PATTERNS,
            Intent.SUPPORT: DEFAULT_SUPPORT_PATTERNS,
        }

    def process(self, input_data: Input) -> Output:
        """Process input data and return output.

        Uses regex pattern matching with priority-based conflict resolution.
        CRISIS > SEEDING = SPAM > COMPLAINT > LEAD > SUPPORT > DISCUSSION

        Args:
            input_data: Input structure with text

        Returns:
            Output with intent, confidence, should_skip flag, and matched patterns

        Raises:
            ValueError: If input_data is invalid
            Exception: If processing fails
        """
        if not isinstance(input_data, Input):
            error_msg = "input_data must be an instance of Input"
            if self.logger:
                self.logger.error(
                    "[IntentClassification] Invalid input type",
                    extra={"input_type": type(input_data).__name__},
                )
            raise ValueError(error_msg)

        try:
            text = input_data.text

            if self.logger:
                self.logger.debug(
                    "[IntentClassification] Processing started",
                    extra={"text_len": len(text)},
                )

            # Handle empty/None input
            if not text:
                if self.logger:
                    self.logger.info(
                        "[IntentClassification] Empty text, defaulting to DISCUSSION"
                    )
                return Output(
                    intent=Intent.DISCUSSION,
                    confidence=CONFIDENCE_MAX,
                    should_skip=False,
                    matched_patterns=[],
                )

            # Track matches: {intent: [matched_pattern_strings]}
            matches: dict[Intent, list[str]] = {}

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
                if self.logger:
                    self.logger.info(
                        "[IntentClassification] No patterns matched, defaulting to DISCUSSION"
                    )
                return Output(
                    intent=Intent.DISCUSSION,
                    confidence=CONFIDENCE_MAX,
                    should_skip=False,
                    matched_patterns=[],
                )

            # Resolve conflicts by priority (highest priority wins)
            best_intent = max(matches.keys(), key=lambda i: i.priority)
            matched_patterns = matches[best_intent]

            # Calculate confidence based on number of matches
            num_matches = len(matched_patterns)
            confidence = min(
                CONFIDENCE_BASE + (num_matches * CONFIDENCE_INCREMENT), CONFIDENCE_MAX
            )

            # Determine if we should skip AI processing
            # SPAM and SEEDING should be skipped
            should_skip = best_intent in (Intent.SPAM, Intent.SEEDING)

            if self.logger:
                self.logger.info(
                    "[IntentClassification] Processing completed",
                    extra={
                        "intent": best_intent.name,
                        "confidence": confidence,
                        "should_skip": should_skip,
                        "num_matches": num_matches,
                    },
                )

            return Output(
                intent=best_intent,
                confidence=confidence,
                should_skip=should_skip,
                matched_patterns=matched_patterns,
            )

        except ValueError:
            raise
        except Exception as e:
            if self.logger:
                self.logger.error(
                    "[IntentClassification] Processing failed",
                    extra={"error": str(e), "error_type": type(e).__name__},
                )
            raise


__all__ = ["IntentClassification"]
