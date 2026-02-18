import time
from typing import Optional

from pkg.logger.logger import Logger
from pkg.spacy_yake.spacy_yake import SpacyYake
from internal.keyword_extraction.type import Config, Input, Output, Metadata, Aspect
from internal.keyword_extraction.constant import ASPECT_GENERAL
from .helpers import match_dictionary, extract_ai, fuzzy_map_aspect


def process(
    input_data: Input,
    config: Config,
    aspect_dict: dict[Aspect, dict[str, list[str]]],
    keyword_map: dict[str, Aspect],
    ai_extractor: SpacyYake,
    logger: Optional[Logger] = None,
) -> Output:
    try:
        start_time = time.perf_counter()
        text = input_data.text

        logger.debug("internal.keyword_extraction.usecase.process: Processing started", extra={"text_len": len(text)})

        # Handle empty input
        if not text or not text.strip():
            logger.info("internal.keyword_extraction.usecase.process: Empty text, returning empty result")
            return Output(
                keywords=[],
                metadata=Metadata(
                    dict_matches=0,
                    ai_matches=0,
                    total_keywords=0,
                    total_time_ms=0.0,
                ),
            )

        # Stage 1: Dictionary Matching
        dict_keywords = match_dictionary(text, keyword_map)
        dict_terms = {kw.keyword for kw in dict_keywords}

        # Stage 2: AI Discovery (only if dictionary matches insufficient)
        ai_keywords = []
        if len(dict_keywords) < config.ai_threshold:
            ai_keywords = extract_ai(
                text=text,
                exclude_terms=dict_terms,
                ai_extractor=ai_extractor,
                config=config,
                logger=logger,
            )

            # Stage 3: Aspect Mapping for AI keywords
            for kw in ai_keywords:
                if kw.aspect == ASPECT_GENERAL:
                    mapped_aspect = fuzzy_map_aspect(kw.keyword, keyword_map)
                    kw.aspect = mapped_aspect.value

        # Combine results
        all_keywords = dict_keywords + ai_keywords

        # Remove duplicates (prioritize DICT over AI by keeping first occurrence)
        seen_keywords: set[str] = set()
        unique_keywords = []
        for kw in all_keywords:
            if kw.keyword not in seen_keywords:
                unique_keywords.append(kw)
                seen_keywords.add(kw.keyword)

        # Sort by score descending
        unique_keywords.sort(key=lambda x: x.score, reverse=True)

        # Limit to max_keywords
        final_keywords = unique_keywords[: config.max_keywords]

        # Build metadata
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        metadata = Metadata(
            dict_matches=len(dict_keywords),
            ai_matches=len(ai_keywords),
            total_keywords=len(final_keywords),
            total_time_ms=round(elapsed_ms, 2),
        )

        logger.info("internal.keyword_extraction.usecase.process: Processing completed", extra={"dict_matches": metadata.dict_matches, "ai_matches": metadata.ai_matches, "total_keywords": metadata.total_keywords, "total_time_ms": metadata.total_time_ms})

        return Output(keywords=final_keywords, metadata=metadata)

    except Exception as e:
        logger.error("internal.keyword_extraction.usecase.process: Processing failed", extra={"error": str(e), "error_type": type(e).__name__})
        raise
