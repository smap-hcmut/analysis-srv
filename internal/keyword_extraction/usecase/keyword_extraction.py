"""Keyword Extraction use case.

This module implements a 3-stage hybrid approach:
1. Dictionary Matching - Fast O(n) lookup in aspect dictionary
2. AI Discovery - Use SpaCy+YAKE for new keyword discovery
3. Aspect Mapping - Map all keywords to business aspects

The hybrid approach ensures both precision (dictionary) and recall (AI discovery).
"""

import time
import yaml
from pathlib import Path
from typing import Optional

from pkg.logger.logger import Logger
from pkg.spacy_yake.spacy_yake import SpacyYake
from internal.keyword_extraction.interface import IKeywordExtraction
from internal.keyword_extraction.type import *
from internal.keyword_extraction.constant import *


class KeywordExtraction(IKeywordExtraction):
    """Hybrid keyword extractor with aspect mapping."""

    def __init__(
        self,
        config: Config,
        ai_extractor: SpacyYake,
        logger: Optional[Logger] = None,
    ):
        """Initialize keyword extraction use case.

        Args:
            config: Configuration for keyword extraction
            ai_extractor: SpacyYake instance for AI-powered extraction
            logger: Logger instance (optional). If None, no logging will be performed.
        """
        self.config = config
        self.ai_extractor = ai_extractor
        self.logger = logger

        # Load aspect dictionary
        self.aspect_dict: dict[Aspect, dict[str, list[str]]] = {}
        self.keyword_map: dict[str, Aspect] = {}

        self._load_aspects()
        self._build_lookup_map()

        if self.logger:
            self.logger.info(
                "[KeywordExtraction] Initialized",
                extra={
                    "aspect_dictionary_path": self.config.aspect_dictionary_path,
                    "enable_ai": self.config.enable_ai,
                    "ai_threshold": self.config.ai_threshold,
                    "max_keywords": self.config.max_keywords,
                    "aspects_loaded": len(self.aspect_dict),
                    "keywords_in_dict": len(self.keyword_map),
                },
            )

    def _load_aspects(self) -> None:
        """Load aspect dictionary from YAML configuration file."""
        if not self.config.aspect_dictionary_path:
            self.aspect_dict = {}
            if self.logger:
                self.logger.info(
                    "[KeywordExtraction] No aspect dictionary path configured, using empty dict"
                )
            return

        try:
            dict_path = Path(self.config.aspect_dictionary_path)
            if not dict_path.exists():
                self.aspect_dict = {}
                if self.logger:
                    self.logger.warn(
                        "[KeywordExtraction] Aspect dictionary file not found",
                        extra={"path": str(dict_path)},
                    )
                return

            with open(dict_path, "r", encoding=FILE_ENCODING_UTF8) as f:
                config_data = yaml.safe_load(f)

            if not config_data:
                self.aspect_dict = {}
                return

            # Convert string keys to Aspect enum
            for aspect_name, terms_dict in config_data.items():
                try:
                    aspect = Aspect[aspect_name.upper()]
                    self.aspect_dict[aspect] = terms_dict
                except KeyError:
                    if self.logger:
                        self.logger.warn(
                            "[KeywordExtraction] Invalid aspect in dictionary",
                            extra={"aspect_name": aspect_name},
                        )
                    continue

            if self.logger:
                self.logger.info(
                    "[KeywordExtraction] Aspect dictionary loaded",
                    extra={
                        "path": str(dict_path),
                        "aspects_loaded": len(self.aspect_dict),
                    },
                )

        except Exception as e:
            self.aspect_dict = {}
            if self.logger:
                self.logger.error(
                    "[KeywordExtraction] Failed to load aspect dictionary",
                    extra={"error": str(e), "error_type": type(e).__name__},
                )

    def _build_lookup_map(self) -> None:
        """Build flattened lookup map: keyword → aspect for O(1) lookup."""
        self.keyword_map = {}

        for aspect, terms_dict in self.aspect_dict.items():
            # Add primary terms
            if DICT_KEY_PRIMARY in terms_dict:
                for term in terms_dict[DICT_KEY_PRIMARY]:
                    self.keyword_map[term.lower()] = aspect

            # Add secondary terms
            if DICT_KEY_SECONDARY in terms_dict:
                for term in terms_dict[DICT_KEY_SECONDARY]:
                    self.keyword_map[term.lower()] = aspect

        if self.logger:
            self.logger.debug(
                "[KeywordExtraction] Lookup map built",
                extra={"total_keywords": len(self.keyword_map)},
            )

    def _match_dictionary(self, text: str) -> list[KeywordItem]:
        """Match keywords from dictionary using O(n) word scanning.

        Args:
            text: Input text to scan

        Returns:
            List of matched keywords with aspect labels
        """
        matches = []
        text_lower = text.lower()
        words = text_lower.split()
        matched_terms: set[str] = set()

        # Check each term in dictionary against text
        for term, aspect in self.keyword_map.items():
            # Skip if already matched
            if term in matched_terms:
                continue

            # Check for whole word match or multi-word term
            if term in words or term in text_lower:
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

    def _extract_ai(self, text: str, exclude_terms: set[str]) -> list[KeywordItem]:
        """Extract keywords using AI (SpaCy + YAKE).

        Args:
            text: Input text
            exclude_terms: Terms already matched by dictionary (to avoid duplicates)

        Returns:
            List of AI-discovered keywords
        """
        if not self.config.enable_ai:
            return []

        try:
            # Use SpacyYake extractor
            ai_result = self.ai_extractor.extract(text)

            # Check if AI extraction succeeded
            if not ai_result.success or not ai_result.keywords:
                if self.logger:
                    self.logger.warn(
                        "[KeywordExtraction] AI extraction failed or returned no keywords",
                        extra={"error": ai_result.error_message},
                    )
                return []

            ai_keywords = []
            for kw in ai_result.keywords[: self.config.max_keywords]:
                keyword_lower = kw.keyword.lower()

                # Skip if already in dictionary matches
                if keyword_lower in exclude_terms:
                    continue

                # Keep statistical keywords and entities
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
                        aspect=ASPECT_GENERAL,  # Will be mapped in next stage
                        score=kw.score,
                        source=SOURCE_AI,
                    )
                )

            return ai_keywords

        except Exception as e:
            if self.logger:
                self.logger.error(
                    "[KeywordExtraction] AI extraction error",
                    extra={"error": str(e), "error_type": type(e).__name__},
                )
            return []

    def _fuzzy_map_aspect(self, keyword: str) -> Aspect:
        """Map AI-discovered keyword to aspect using fuzzy matching.

        Args:
            keyword: Keyword to map

        Returns:
            Aspect (GENERAL if no match found)
        """
        keyword_lower = keyword.lower()

        # Check for exact match first
        if keyword_lower in self.keyword_map:
            return self.keyword_map[keyword_lower]

        # Check for substring matches in dictionary terms
        for term, aspect in self.keyword_map.items():
            if term in keyword_lower or keyword_lower in term:
                return aspect

        # Fallback to GENERAL
        return Aspect.GENERAL

    def process(self, input_data: Input) -> Output:
        """Process input data and return output.

        Combines dictionary-based matching with AI discovery to provide
        both high precision (known terms) and high recall (new terms).

        Args:
            input_data: Input structure with text

        Returns:
            Output with keywords and metadata

        Raises:
            ValueError: If input_data is invalid
            Exception: If processing fails
        """
        if not isinstance(input_data, Input):
            error_msg = "input_data must be an instance of Input"
            if self.logger:
                self.logger.error(
                    "[KeywordExtraction] Invalid input type",
                    extra={"input_type": type(input_data).__name__},
                )
            raise ValueError(error_msg)

        try:
            start_time = time.perf_counter()
            text = input_data.text

            if self.logger:
                self.logger.debug(
                    "[KeywordExtraction] Processing started",
                    extra={"text_len": len(text)},
                )

            # Handle empty input
            if not text or not text.strip():
                if self.logger:
                    self.logger.info(
                        "[KeywordExtraction] Empty text, returning empty result"
                    )
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
            dict_keywords = self._match_dictionary(text)
            dict_terms = {kw.keyword for kw in dict_keywords}

            # Stage 2: AI Discovery (only if dictionary matches insufficient)
            ai_keywords = []
            if len(dict_keywords) < self.config.ai_threshold:
                ai_keywords = self._extract_ai(text, dict_terms)

                # Stage 3: Aspect Mapping for AI keywords
                for kw in ai_keywords:
                    if kw.aspect == ASPECT_GENERAL:
                        mapped_aspect = self._fuzzy_map_aspect(kw.keyword)
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
            final_keywords = unique_keywords[: self.config.max_keywords]

            # Build metadata
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            metadata = Metadata(
                dict_matches=len(dict_keywords),
                ai_matches=len(ai_keywords),
                total_keywords=len(final_keywords),
                total_time_ms=round(elapsed_ms, 2),
            )

            if self.logger:
                self.logger.info(
                    "[KeywordExtraction] Processing completed",
                    extra={
                        "dict_matches": metadata.dict_matches,
                        "ai_matches": metadata.ai_matches,
                        "total_keywords": metadata.total_keywords,
                        "total_time_ms": metadata.total_time_ms,
                    },
                )

            return Output(keywords=final_keywords, metadata=metadata)

        except ValueError:
            raise
        except Exception as e:
            if self.logger:
                self.logger.error(
                    "[KeywordExtraction] Processing failed",
                    extra={"error": str(e), "error_type": type(e).__name__},
                )
            raise


__all__ = ["KeywordExtraction"]
