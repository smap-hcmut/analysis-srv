from typing import Pattern as RePattern

from pkg.logger.logger import Logger
from internal.intent_classification.type import Input, Output, Intent
from internal.intent_classification.constant import (
    CONFIDENCE_MAX,
    CONFIDENCE_BASE,
    CONFIDENCE_INCREMENT,
)


def process(
    input_data: Input,
    patterns: dict[Intent, list[RePattern]],
    logger: Logger,
) -> Output:
    try:
        text = input_data.text

        logger.debug("internal.intent_classification.usecase.process: Processing started", extra={"text_len": len(text)})

        if not text:
            logger.info("internal.intent_classification.usecase.process: Empty text, defaulting to DISCUSSION")
            return Output(
                intent=Intent.DISCUSSION,
                confidence=CONFIDENCE_MAX,
                should_skip=False,
                matched_patterns=[],
            )

        matches: dict[Intent, list[str]] = {}

        for intent, intent_patterns in patterns.items():
            matched = []
            for pattern in intent_patterns:
                if pattern.search(text):
                    matched.append(pattern.pattern)

            if matched:
                matches[intent] = matched

        if not matches:
            logger.info("internal.intent_classification.usecase.process: No patterns matched, defaulting to DISCUSSION")
            return Output(
                intent=Intent.DISCUSSION,
                confidence=CONFIDENCE_MAX,
                should_skip=False,
                matched_patterns=[],
            )

        best_intent = max(matches.keys(), key=lambda i: i.priority)
        matched_patterns = matches[best_intent]

        num_matches = len(matched_patterns)
        confidence = min(
            CONFIDENCE_BASE + (num_matches * CONFIDENCE_INCREMENT), CONFIDENCE_MAX
        )

        should_skip = best_intent in (Intent.SPAM, Intent.SEEDING)

        logger.info("internal.intent_classification.usecase.process: Processing completed", extra={"intent": best_intent.name, "confidence": confidence, "should_skip": should_skip, "num_matches": num_matches})

        return Output(
            intent=best_intent,
            confidence=confidence,
            should_skip=should_skip,
            matched_patterns=matched_patterns,
        )

    except Exception as e:
        logger.error("internal.intent_classification.usecase.process: Processing failed", extra={"error": str(e), "error_type": type(e).__name__})
        raise
