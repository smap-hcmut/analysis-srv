"""SpaCy + YAKE keyword extraction wrapper.

This module provides a wrapper for SpaCy and YAKE-based keyword extraction,
following the same pattern as PhoBERT ONNX integration.
"""

import logging
import numpy as np  # type: ignore
from typing import Dict, List, Optional, Union, Any
from dataclasses import dataclass, field

try:
    import spacy  # type: ignore
except ImportError:
    spacy = None  # type: ignore

try:
    import yake  # type: ignore
except ImportError:
    yake = None  # type: ignore

from infrastructure.ai.constants import (
    DEFAULT_SPACY_MODEL,
    DEFAULT_YAKE_LANGUAGE,
    DEFAULT_YAKE_N,
    DEFAULT_YAKE_DEDUP_LIM,
    DEFAULT_YAKE_MAX_KEYWORDS,
    DEFAULT_MAX_KEYWORDS,
    DEFAULT_ENTITY_WEIGHT,
    DEFAULT_CHUNK_WEIGHT,
    ERROR_MODEL_NOT_INITIALIZED,
    ERROR_INVALID_INPUT,
)


@dataclass
class ExtractionResult:
    """Result of keyword extraction operation."""

    keywords: List[Dict[str, Union[str, float, int]]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    method_name: str = "spacy_yake"
    confidence_score: float = 0.0
    success: bool = True
    error_message: Optional[str] = None


class SpacyYakeExtractor:
    """SpaCy + YAKE wrapper for keyword extraction.

    This class handles:
    - Named entity recognition using SpaCy
    - Noun chunk extraction using SpaCy
    - Statistical keyword extraction using YAKE
    - Keyword combination and scoring

    Attributes:
        spacy_model: Name of SpaCy model to use
        nlp: SpaCy model instance
        yake_extractor: YAKE extractor instance
        max_keywords: Maximum number of keywords to return
    """

    def __init__(
        self,
        spacy_model: str = DEFAULT_SPACY_MODEL,
        yake_language: str = DEFAULT_YAKE_LANGUAGE,
        yake_n: int = DEFAULT_YAKE_N,
        yake_dedup_lim: float = DEFAULT_YAKE_DEDUP_LIM,
        yake_max_keywords: int = DEFAULT_YAKE_MAX_KEYWORDS,
        max_keywords: int = DEFAULT_MAX_KEYWORDS,
        entity_weight: float = DEFAULT_ENTITY_WEIGHT,
        chunk_weight: float = DEFAULT_CHUNK_WEIGHT,
    ):
        """Initialize SpaCy and YAKE extractors.

        Args:
            spacy_model: SpaCy model name (e.g., 'en_core_web_sm')
            yake_language: Language code for YAKE (e.g., 'en', 'vi')
            yake_n: Max n-gram size for YAKE
            yake_dedup_lim: Deduplication threshold for YAKE
            yake_max_keywords: Max keywords to extract with YAKE
            max_keywords: Max keywords to return in final result
            entity_weight: Score weight for named entities
            chunk_weight: Score weight for noun chunks

        Raises:
            ImportError: If spaCy or YAKE libraries are not installed
            OSError: If SpaCy model is not found
        """
        self.spacy_model = spacy_model
        self.max_keywords = max_keywords
        self.entity_weight = entity_weight
        self.chunk_weight = chunk_weight
        self.logger = logging.getLogger(__name__)

        # Initialize SpaCy
        if spacy is None:
            self.logger.error("Failed to import spaCy")
            self.nlp = None
            raise ImportError("spaCy is not installed")

        try:
            self.nlp = spacy.load(spacy_model)
            self.logger.info(f"Loaded SpaCy model: {spacy_model}")
        except OSError:
            self.logger.warning(f"Model {spacy_model} not found, attempting download")
            spacy.cli.download(spacy_model)
            self.nlp = spacy.load(spacy_model)

        # Initialize YAKE
        if yake is None:
            self.logger.error("Failed to import YAKE")
            self.yake_extractor = None
            raise ImportError("yake is not installed")

        yake_config = {
            "lan": yake_language,
            "n": yake_n,
            "dedupLim": yake_dedup_lim,
            "top": yake_max_keywords,
            "features": None,
        }
        self.yake_extractor = yake.KeywordExtractor(**yake_config)
        self.logger.info(f"Initialized YAKE with config: {yake_config}")

    def _validate_text(self, text: str) -> bool:
        """Validate input text.

        Args:
            text: Input text to validate

        Returns:
            True if text is valid, False otherwise
        """
        if not isinstance(text, str):
            return False
        if not text or not text.strip():
            return False
        if len(text) > 10000:
            self.logger.warning(f"Text length {len(text)} exceeds recommended limit")
        return True

    def _extract_entities(self, doc) -> List[tuple]:
        """Extract and filter named entities.

        Args:
            doc: SpaCy Doc object

        Returns:
            List of (entity_text, entity_label) tuples
        """
        entities = []
        for ent in doc.ents:
            # Filter entities by quality criteria
            if len(ent.text.split()) <= 3 and len(ent.text.strip()) > 1 and not ent.text.isdigit():
                entities.append((ent.text.strip(), ent.label_))
        return entities[:15]  # Limit to top 15

    def _extract_noun_chunks(self, doc) -> List[str]:
        """Extract and filter noun chunks.

        Args:
            doc: SpaCy Doc object

        Returns:
            List of noun chunk strings
        """
        chunks = []
        for chunk in doc.noun_chunks:
            # Filter chunks by relevance criteria
            if (
                len(chunk.text.split()) >= 2
                and len(chunk.text.split()) <= 4
                and len(chunk.text.strip()) > 3
            ):
                chunks.append(chunk.text.strip())
        return chunks[:20]  # Limit to top 20

    def _combine_keyword_sources(
        self, yake_keywords: List[tuple], entities: List[tuple], noun_chunks: List[str]
    ) -> List[Dict]:
        """Combine keywords from different sources with appropriate scoring.

        Args:
            yake_keywords: List of (keyword, score) from YAKE
            entities: List of (entity, label) from SpaCy
            noun_chunks: List of noun chunks from SpaCy

        Returns:
            Combined and sorted list of keyword dictionaries
        """
        keywords = []

        # Add YAKE keywords (statistical)
        for i, (keyword, score) in enumerate(yake_keywords):
            keywords.append(
                {
                    "keyword": keyword.strip(),
                    "score": 1.0 - score,  # YAKE: lower is better, so invert
                    "rank": i + 1,
                    "type": "statistical",
                    "relevance": 1.0 - score,
                }
            )

        # Add named entities (linguistic)
        for entity, label in entities:
            keywords.append(
                {
                    "keyword": entity,
                    "score": self.entity_weight,
                    "rank": len(keywords) + 1,
                    "type": f"entity_{label.lower()}",
                    "relevance": self.entity_weight,
                }
            )

        # Add noun chunks (syntactic)
        for chunk in noun_chunks:
            keywords.append(
                {
                    "keyword": chunk,
                    "score": self.chunk_weight,
                    "rank": len(keywords) + 1,
                    "type": "syntactic",
                    "relevance": self.chunk_weight,
                }
            )

        # Sort by score descending
        keywords.sort(key=lambda x: x["score"], reverse=True)

        # Re-rank after sorting
        for i, kw in enumerate(keywords):
            kw["rank"] = i + 1

        return keywords

    def _calculate_confidence(
        self, keywords: List[Dict], entities: List[tuple], noun_chunks: List[str]
    ) -> float:
        """Calculate confidence score based on extraction quality.

        Args:
            keywords: List of extracted keywords
            entities: List of named entities
            noun_chunks: List of noun chunks

        Returns:
            Confidence score between 0.0 and 1.0
        """
        if not keywords:
            return 0.0

        # Base confidence from keyword count and quality
        keyword_count_score = min(len(keywords) / 30.0, 1.0)

        # Diversity bonus from different source types
        source_types = set(kw["type"] for kw in keywords)
        diversity_bonus = min(len(source_types) / 4.0, 0.2)

        # Entity quality bonus
        entity_types = set(label for _, label in entities) if entities else set()
        entity_bonus = min(len(entity_types) / 5.0, 0.15)

        # Score distribution quality
        scores = [kw["score"] for kw in keywords]
        score_variance = np.var(scores) if len(scores) > 1 else 0
        variance_bonus = min(score_variance, 0.15)

        # Combine all factors
        confidence = keyword_count_score + diversity_bonus + entity_bonus + variance_bonus
        return min(confidence, 1.0)

    def extract(self, text: str) -> ExtractionResult:
        """Extract keywords from text.

        Args:
            text: Input text to extract keywords from

        Returns:
            ExtractionResult with keywords and metadata

        Example:
            >>> extractor = SpacyYakeExtractor()
            >>> result = extractor.extract("This is a great product with excellent quality")
            >>> print(result.keywords[:3])
            [
                {'keyword': 'great product', 'score': 0.95, 'rank': 1, 'type': 'statistical'},
                {'keyword': 'excellent quality', 'score': 0.90, 'rank': 2, 'type': 'statistical'},
                ...
            ]
        """
        # Validate input
        if not self._validate_text(text):
            return ExtractionResult(
                success=False,
                error_message=ERROR_INVALID_INPUT,
                metadata={"error": ERROR_INVALID_INPUT},
            )

        # Check if models are loaded
        if not self.nlp or not self.yake_extractor:
            return ExtractionResult(
                success=False,
                error_message=ERROR_MODEL_NOT_INITIALIZED,
                metadata={"error": ERROR_MODEL_NOT_INITIALIZED},
            )

        try:
            # Process with SpaCy for linguistic features
            doc = self.nlp(text)

            # Extract linguistic features
            entities = self._extract_entities(doc)
            noun_chunks = self._extract_noun_chunks(doc)

            # Extract statistical keywords with YAKE
            yake_keywords = self.yake_extractor.extract_keywords(text)

            # Combine and score all keywords
            keywords = self._combine_keyword_sources(yake_keywords, entities, noun_chunks)

            # Calculate confidence score
            confidence = self._calculate_confidence(keywords, entities, noun_chunks)

            # Limit results based on configuration
            final_keywords = keywords[: self.max_keywords]

            # Build metadata
            metadata = {
                "method": "spacy_yake",
                "entities_count": len(entities),
                "noun_chunks_count": len(noun_chunks),
                "yake_keywords_count": len(yake_keywords),
                "total_candidates": len(keywords),
                "final_count": len(final_keywords),
            }

            return ExtractionResult(
                keywords=final_keywords,
                metadata=metadata,
                confidence_score=confidence,
                success=True,
            )

        except Exception as e:
            self.logger.error(f"Error during extraction: {str(e)}")
            return ExtractionResult(success=False, error_message=str(e), metadata={"error": str(e)})

    def extract_batch(self, texts: List[str]) -> List[ExtractionResult]:
        """Extract keywords from multiple texts.

        Args:
            texts: List of input texts

        Returns:
            List of ExtractionResult objects
        """
        return [self.extract(text) for text in texts]
