"""Hybrid Keyword Extractor with Aspect Mapping.

This module implements a 3-stage hybrid approach:
1. Dictionary Matching - Fast O(n) lookup in aspect dictionary
2. AI Discovery - Use SpaCy+YAKE for new keyword discovery
3. Aspect Mapping - Map all keywords to business aspects

The hybrid approach ensures both precision (dictionary) and recall (AI discovery).
"""

import time
import yaml
from pathlib import Path
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Set

from infrastructure.ai import SpacyYakeExtractor
from core.config import settings


class Aspect(Enum):
    """Business aspects for automotive analytics.

    Each aspect represents a category of customer feedback that's
    actionable for business decisions.
    """

    DESIGN = "DESIGN"  # Exterior/interior appearance, aesthetics
    PERFORMANCE = "PERFORMANCE"  # Battery, charging, speed, technical issues
    PRICE = "PRICE"  # Cost, value, affordability
    SERVICE = "SERVICE"  # Customer service, warranty, support
    GENERAL = "GENERAL"  # Default for unclassified keywords

    def __str__(self) -> str:
        """String representation."""
        return self.value


@dataclass
class KeywordResult:
    """Result of hybrid keyword extraction.

    Attributes:
        keywords: List of extracted keywords with aspect labels
        metadata: Extraction statistics and timing info
    """

    keywords: List[Dict[str, any]]
    metadata: Dict[str, any]


class KeywordExtractor:
    """Hybrid keyword extractor with aspect mapping.

    Combines dictionary-based matching (high precision) with AI-powered
    discovery (high recall) to extract aspect-aware keywords from text.

    Example:
        >>> extractor = KeywordExtractor()
        >>> result = extractor.extract("Xe đẹp nhưng pin yếu quá")
        >>> print(result.keywords)
        [
            {"keyword": "pin", "aspect": "PERFORMANCE", "score": 1.0, "source": "DICT"},
            {"keyword": "xe", "aspect": "GENERAL", "score": 0.85, "source": "AI"}
        ]
        >>> print(result.metadata)
        {"dict_matches": 1, "ai_matches": 1, "total_time_ms": 12.5}
    """

    def __init__(self):
        """Initialize extractor with aspect dictionary and AI model."""
        # Lazy-load AI extractor to avoid initialization errors
        self._ai_extractor = None

        # Load aspect dictionary
        self.aspect_dict: Dict[Aspect, Dict[str, List[str]]] = {}
        self.keyword_map: Dict[str, Aspect] = {}

        # Configuration
        # Note: enable_ai defaults to True for full hybrid functionality
        self.enable_ai = getattr(settings, "enable_aspect_mapping", True)
        self.ai_threshold = 5  # Run AI if dict matches < threshold
        self.max_keywords = settings.max_keywords if hasattr(settings, "max_keywords") else 30

        # Load dictionary
        self._load_aspects()
        self._build_lookup_map()

    @property
    def ai_extractor(self):
        """Lazy-load AI extractor on first access."""
        if self._ai_extractor is None and self.enable_ai:
            self._ai_extractor = SpacyYakeExtractor()
        return self._ai_extractor

    def _load_aspects(self) -> None:
        """Load aspect dictionary from YAML configuration file."""
        try:
            dict_path = Path(settings.aspect_dictionary_path)
            if not dict_path.exists():
                # Use empty dict if file doesn't exist
                self.aspect_dict = {}
                return

            with open(dict_path, "r", encoding="utf-8") as f:
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
                    continue  # Skip invalid aspects
        except Exception:
            # Fallback to empty dict on any error
            self.aspect_dict = {}

    def _build_lookup_map(self) -> None:
        """Build flattened lookup map: keyword → aspect for O(1) lookup."""
        self.keyword_map = {}

        for aspect, terms_dict in self.aspect_dict.items():
            # Add primary terms
            if "primary" in terms_dict:
                for term in terms_dict["primary"]:
                    self.keyword_map[term.lower()] = aspect

            # Add secondary terms
            if "secondary" in terms_dict:
                for term in terms_dict["secondary"]:
                    self.keyword_map[term.lower()] = aspect

    def _match_dictionary(self, text: str) -> List[Dict[str, any]]:
        """Match keywords from dictionary using O(n) word scanning.

        Args:
            text: Input text to scan

        Returns:
            List of matched keywords with aspect labels
        """
        matches = []
        text_lower = text.lower()
        words = text_lower.split()
        matched_terms: Set[str] = set()

        # Check each term in dictionary against text
        for term, aspect in self.keyword_map.items():
            # Skip if already matched
            if term in matched_terms:
                continue

            # Check for whole word match or multi-word term
            if term in words or term in text_lower:
                matches.append(
                    {
                        "keyword": term,
                        "aspect": aspect.value,
                        "score": 1.0,  # Dictionary matches have perfect score
                        "source": "DICT",
                    }
                )
                matched_terms.add(term)

        return matches

    def _extract_ai(self, text: str, exclude_terms: Set[str]) -> List[Dict[str, any]]:
        """Extract keywords using AI (SpaCy + YAKE).

        Args:
            text: Input text
            exclude_terms: Terms already matched by dictionary (to avoid duplicates)

        Returns:
            List of AI-discovered keywords
        """
        if not self.enable_ai:
            return []

        try:
            # Use existing SpaCy+YAKE extractor
            ai_result = self.ai_extractor.extract(text)

            # Check if AI extraction succeeded
            if not ai_result.success or not ai_result.keywords:
                return []

            ai_keywords = []
            for kw in ai_result.keywords[: self.max_keywords]:
                keyword_lower = kw["keyword"].lower()

                # Skip if already in dictionary matches
                if keyword_lower in exclude_terms:
                    continue

                # Keep statistical keywords and entities
                # SpaCyYakeExtractor returns types: 'statistical', 'entity_*', 'chunk'
                kw_type = kw.get("type", "")
                if not (kw_type == "statistical" or kw_type.startswith("entity") or kw_type == "chunk"):
                    continue

                ai_keywords.append(
                    {
                        "keyword": keyword_lower,
                        "aspect": "GENERAL",  # Will be mapped in next stage
                        "score": kw.get("score", 0.5),
                        "source": "AI",
                    }
                )

            return ai_keywords
        except Exception:
            # Return empty list on any AI extraction error
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

    def extract(self, text: str) -> KeywordResult:
        """Extract keywords with aspect mapping using hybrid approach.

        Combines dictionary-based matching with AI discovery to provide
        both high precision (known terms) and high recall (new terms).

        Args:
            text: Input text to extract keywords from

        Returns:
            KeywordResult with keywords and metadata

        Example:
            >>> extractor = KeywordExtractor()
            >>> result = extractor.extract("Xe pin yếu, giá đắt")
            >>> for kw in result.keywords:
            ...     print(f"{kw['keyword']} → {kw['aspect']} ({kw['source']})")
            pin → PERFORMANCE (DICT)
            giá → PRICE (DICT)
            xe → GENERAL (AI)
        """
        start_time = time.perf_counter()

        # Handle empty input
        if not text or not text.strip():
            return KeywordResult(
                keywords=[], metadata={"dict_matches": 0, "ai_matches": 0, "total_time_ms": 0.0}
            )

        # Stage 1: Dictionary Matching
        dict_keywords = self._match_dictionary(text)
        dict_terms = {kw["keyword"] for kw in dict_keywords}

        # Stage 2: AI Discovery (only if dictionary matches insufficient)
        ai_keywords = []
        if len(dict_keywords) < self.ai_threshold:
            ai_keywords = self._extract_ai(text, dict_terms)

            # Stage 3: Aspect Mapping for AI keywords
            for kw in ai_keywords:
                if kw["aspect"] == "GENERAL":
                    mapped_aspect = self._fuzzy_map_aspect(kw["keyword"])
                    kw["aspect"] = mapped_aspect.value

        # Combine results
        all_keywords = dict_keywords + ai_keywords

        # Remove duplicates (prioritize DICT over AI by keeping first occurrence)
        seen_keywords: Set[str] = set()
        unique_keywords = []
        for kw in all_keywords:
            if kw["keyword"] not in seen_keywords:
                unique_keywords.append(kw)
                seen_keywords.add(kw["keyword"])

        # Sort by score descending
        unique_keywords.sort(key=lambda x: x["score"], reverse=True)

        # Limit to max_keywords
        final_keywords = unique_keywords[: self.max_keywords]

        # Build metadata
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        metadata = {
            "dict_matches": len(dict_keywords),
            "ai_matches": len(ai_keywords),
            "total_keywords": len(final_keywords),
            "total_time_ms": round(elapsed_ms, 2),
        }

        return KeywordResult(keywords=final_keywords, metadata=metadata)
