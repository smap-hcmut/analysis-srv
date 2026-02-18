import re
import yaml
from pathlib import Path
from typing import Pattern as RePattern

from pkg.logger.logger import Logger
from internal.intent_classification.type import Config, Intent
from internal.intent_classification.constant import (
    FILE_ENCODING_UTF8,
    DEFAULT_CRISIS_PATTERNS,
    DEFAULT_SEEDING_PATTERNS,
    DEFAULT_SPAM_PATTERNS,
    DEFAULT_COMPLAINT_PATTERNS,
    DEFAULT_LEAD_PATTERNS,
    DEFAULT_SUPPORT_PATTERNS,
)


def get_default_patterns() -> dict[Intent, list[str]]:
    return {
        Intent.CRISIS: DEFAULT_CRISIS_PATTERNS,
        Intent.SEEDING: DEFAULT_SEEDING_PATTERNS,
        Intent.SPAM: DEFAULT_SPAM_PATTERNS,
        Intent.COMPLAINT: DEFAULT_COMPLAINT_PATTERNS,
        Intent.LEAD: DEFAULT_LEAD_PATTERNS,
        Intent.SUPPORT: DEFAULT_SUPPORT_PATTERNS,
    }


def load_patterns_from_config(
    config: Config, logger: Logger
) -> dict[Intent, list[str]] | None:
    if not config.patterns_path:
        return None

    try:
        config_path = Path(config.patterns_path)
        if not config_path.exists():
            logger.warn("internal.intent_classification.usecase.helpers: Patterns file not found", extra={"path": str(config_path)})
            return None

        with open(config_path, "r", encoding=FILE_ENCODING_UTF8) as f:
            config_data = yaml.safe_load(f)

        if not config_data:
            return None

        patterns_dict = {}
        for intent_name, patterns in config_data.items():
            try:
                intent = Intent[intent_name.upper()]
                patterns_dict[intent] = patterns
            except KeyError:
                logger.warn("internal.intent_classification.usecase.helpers: Invalid intent in config", extra={"intent_name": intent_name})
                continue

        return patterns_dict

    except Exception as e:
        logger.error("internal.intent_classification.usecase.helpers: Failed to load patterns from config", extra={"error": str(e), "path": config.patterns_path})
        return None


def compile_patterns(config: Config, logger: Logger) -> dict[Intent, list[RePattern]]:
    try:
        patterns_dict = load_patterns_from_config(config, logger)

        if not patterns_dict:
            patterns_dict = get_default_patterns()
            logger.info("internal.intent_classification.usecase.helpers: Using default patterns", extra={"reason": "config_not_found_or_empty"})

        compiled_patterns = {
            intent: [re.compile(pat, re.IGNORECASE) for pat in pattern_strs]
            for intent, pattern_strs in patterns_dict.items()
        }

        pattern_counts = {
            intent.name: len(patterns) for intent, patterns in compiled_patterns.items()
        }
        logger.debug("internal.intent_classification.usecase.helpers: Patterns compiled", extra={"counts": pattern_counts})

        return compiled_patterns

    except Exception as e:
        logger.error("internal.intent_classification.usecase.helpers: Pattern compilation failed", extra={"error": str(e), "error_type": type(e).__name__})
        raise
