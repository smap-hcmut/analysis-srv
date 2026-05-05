import re
import yaml
from pathlib import Path
from typing import Optional

from pkg.logger.logger import Logger
from pkg.spacy_yake.spacy_yake import SpacyYake
from internal.keyword_extraction.type import Config, Aspect, KeywordItem
from internal.keyword_extraction.constant import (
    FILE_ENCODING_UTF8,
    DICT_KEY_PRIMARY,
    DICT_KEY_SECONDARY,
    SCORE_DICT_MATCH,
    SOURCE_DICT,
    SOURCE_AI,
    KEYWORD_TYPE_STATISTICAL,
    KEYWORD_TYPE_ENTITY_PREFIX,
    KEYWORD_TYPE_CHUNK,
    ASPECT_GENERAL,
)

AI_NOISE_TOKENS = {
    "ai",
    "ahamova",
    "bao",
    "ca",
    "cho",
    "cung",
    "cuc",
    "da",
    "dang",
    "day",
    "de",
    "gia",
    "giup",
    "hoi",
    "ib",
    "khach",
    "khong",
    "la",
    "luon",
    "minh",
    "moi",
    "ngay",
    "nguoi",
    "ngay",
    "nghe",
    "nhe",
    "nhieu",
    "noi",
    "o",
    "qua",
    "rat",
    "roi",
    "se",
    "shop",
    "tai",
    "thang",
    "the",
    "thi",
    "thoi",
    "tra",
    "vai",
    "vay",
    "voi",
}


def load_aspects(
    config: Config, logger: Optional[Logger] = None
) -> dict[Aspect, dict[str, list[str]]]:
    if not config.aspect_dictionary_path:
        logger.info(
            "internal.keyword_extraction.usecase.helpers: No aspect dictionary path configured, using empty dict"
        )
        return {}

    try:
        dict_path = Path(config.aspect_dictionary_path)
        if not dict_path.exists():
            logger.warn(
                "internal.keyword_extraction.usecase.helpers: Aspect dictionary file not found",
                extra={"path": str(dict_path)},
            )
            return {}

        with open(dict_path, "r", encoding=FILE_ENCODING_UTF8) as f:
            config_data = yaml.safe_load(f)

        if not config_data:
            return {}

        aspect_dict = {}
        for aspect_name, terms_dict in config_data.items():
            try:
                aspect = Aspect[aspect_name.upper()]
                aspect_dict[aspect] = terms_dict
            except KeyError:
                logger.warn(
                    "internal.keyword_extraction.usecase.helpers: Invalid aspect in dictionary",
                    extra={"aspect_name": aspect_name},
                )
                continue

        return aspect_dict

    except Exception as e:
        logger.error(
            "internal.keyword_extraction.usecase.helpers: Failed to load aspect dictionary",
            extra={"error": str(e), "error_type": type(e).__name__},
        )
        return {}


def build_lookup_map(
    aspect_dict: dict[Aspect, dict[str, list[str]]], logger: Optional[Logger] = None
) -> dict[str, Aspect]:
    keyword_map = {}

    for aspect, terms_dict in aspect_dict.items():
        if DICT_KEY_PRIMARY in terms_dict:
            for term in terms_dict[DICT_KEY_PRIMARY]:
                keyword_map[term.lower()] = aspect

        if DICT_KEY_SECONDARY in terms_dict:
            for term in terms_dict[DICT_KEY_SECONDARY]:
                keyword_map[term.lower()] = aspect

    logger.debug(
        "internal.keyword_extraction.usecase.helpers: Lookup map built",
        extra={"total_keywords": len(keyword_map)},
    )

    return keyword_map


def match_dictionary(text: str, keyword_map: dict[str, Aspect]) -> list[KeywordItem]:
    matches = []
    text_lower = text.lower()
    matched_terms: set[str] = set()

    for term, aspect in keyword_map.items():
        if term in matched_terms:
            continue

        if contains_term(text_lower, term):
            matches.append(
                KeywordItem(
                    keyword=term,
                    aspect=aspect.value,
                    score=SCORE_DICT_MATCH,
                    source=SOURCE_DICT,
                )
            )
            matched_terms.add(term)

    return matches


def contains_term(text: str, term: str) -> bool:
    pattern = rf"(?<!\w){re.escape(term.lower())}(?!\w)"
    return re.search(pattern, text.lower()) is not None


def should_keep_ai_keyword(
    keyword: str,
    aspect: str,
    exclude_terms: set[str],
) -> bool:
    keyword_lower = keyword.strip().lower()
    if not keyword_lower or aspect == ASPECT_GENERAL:
        return False

    tokens = re.findall(r"\w+", keyword_lower)
    if len(tokens) < 2:
        return False

    if any(char.isdigit() for char in keyword_lower):
        return False

    for term in exclude_terms:
        if term != keyword_lower and contains_term(keyword_lower, term):
            return False

    content_tokens = [token for token in tokens if token not in AI_NOISE_TOKENS]
    return len(content_tokens) >= 2


def extract_ai(
    text: str,
    exclude_terms: set[str],
    ai_extractor: SpacyYake,
    config: Config,
    logger: Optional[Logger] = None,
) -> list[KeywordItem]:
    if not config.enable_ai:
        return []

    try:
        ai_result = ai_extractor.extract(text)

        if not ai_result.success or not ai_result.keywords:
            if ai_result.error_message:
                logger.warn(
                    "internal.keyword_extraction.usecase.helpers: AI extraction failed",
                    extra={"error": ai_result.error_message},
                )
            return []

        ai_keywords = []
        for kw in ai_result.keywords[: config.max_keywords]:
            keyword_lower = kw.keyword.lower()

            if keyword_lower in exclude_terms:
                continue

            kw_type = kw.type
            if not (
                kw_type == KEYWORD_TYPE_STATISTICAL
                or kw_type.startswith(KEYWORD_TYPE_ENTITY_PREFIX)
                or kw_type == KEYWORD_TYPE_CHUNK
            ):
                continue

            ai_keywords.append(
                KeywordItem(
                    keyword=keyword_lower,
                    aspect=ASPECT_GENERAL,
                    score=kw.score,
                    source=SOURCE_AI,
                )
            )

        return ai_keywords

    except Exception as e:
        logger.error(
            "internal.keyword_extraction.usecase.helpers: AI extraction error",
            extra={"error": str(e), "error_type": type(e).__name__},
        )
        return []


def fuzzy_map_aspect(keyword: str, keyword_map: dict[str, Aspect]) -> Aspect:
    keyword_lower = keyword.lower()

    if keyword_lower in keyword_map:
        return keyword_map[keyword_lower]

    for term, aspect in keyword_map.items():
        if contains_term(keyword_lower, term) or contains_term(term, keyword_lower):
            return aspect

    return Aspect.GENERAL
