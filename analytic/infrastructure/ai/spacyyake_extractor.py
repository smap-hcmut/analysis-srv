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

        # Smart model loading with graceful fallback
        # Priority order: user model -> multilingual -> blank Vietnamese
        model_loaded = False
        
        # Build fallback chain based on user preference
        fallback_models = [spacy_model]
        
        # If user specified Vietnamese model, add fallbacks
        if "vi_core" in spacy_model:
            # Try smaller Vietnamese model if large fails
            if "_lg" in spacy_model:
                fallback_models.append(spacy_model.replace("_lg", "_sm"))
            elif "_sm" in spacy_model:
                fallback_models.append(spacy_model.replace("_sm", "_lg"))
        
        # Always try multilingual model (official, stable)
        if "xx_ent_wiki_sm" not in fallback_models:
            fallback_models.append("xx_ent_wiki_sm")
        
        # Try English model as additional fallback
        if "en_core_web_sm" not in fallback_models:
            fallback_models.append("en_core_web_sm")
        
        # Try to load from fallback chain
        for model_name in fallback_models:
            try:
                self.nlp = spacy.load(model_name)
                self.logger.info(f"✅ Loaded SpaCy model: {model_name}")
                model_loaded = True
                break
            except OSError:
                continue
        
        # Final fallback: Blank Vietnamese model (tokenizer only)
        if not model_loaded:
            try:
                self.logger.warning(
                    f"⚠️  No pre-trained model found. Using blank 'vi' model (tokenizer only).\n"
                    f"Attempted models: {', '.join(fallback_models)}\n"
                    f"To improve AI Discovery, install multilingual model:\n"
                    f"  uv run python -m spacy download xx_ent_wiki_sm"
                )
                self.nlp = spacy.blank("vi")
                # Blank model needs sentencizer for sentence segmentation
                if "sentencizer" not in self.nlp.pipe_names:
                    self.nlp.add_pipe("sentencizer")
                self.logger.info("✅ Using blank Vietnamese model with sentencizer")
            except Exception as e:
                self.logger.error(f"Failed to create blank model: {e}")
                self.nlp = None

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
        """Extract and filter noun chunks using POS tagging.

        Handles both full models (with POS tagging) and blank models (tokenizer only).
        Uses flexible extraction logic that adapts to model capabilities.

        Note: Uses manual POS-based extraction instead of doc.noun_chunks
        because multilingual models (xx) and some languages don't support
        the noun_chunks iterator.

        Args:
            doc: SpaCy Doc object

        Returns:
            List of noun chunk strings
        """
        chunks = []
        
        # Check if model has POS tagging capability
        has_pos_tagging = any(
            hasattr(token, 'pos_') and token.pos_ 
            for token in doc 
            if hasattr(token, 'pos_')
        )

        # Method 1: Use built-in noun chunks if available (full models)
        if doc.has_annotation("DEP"):
            try:
                for chunk in doc.noun_chunks:
                    text = chunk.text.strip()
                    if len(text) > 1:
                        chunks.append(text)
            except (AttributeError, KeyError):
                # Some models don't support noun_chunks
                pass

        # Method 2: Extract based on POS tags (if model has POS tagging)
        if has_pos_tagging:
            # Extract single nouns and proper nouns
            for token in doc:
                if token.pos_ in ["NOUN", "PROPN"] and not token.is_stop and not token.is_punct:
                    text = token.text.strip()
                    if len(text) > 1:  # Filter out single characters
                        chunks.append(text)

            # Extract simple noun phrases (Noun + Adj, Noun + Noun)
            # Pattern: Noun + Adjective (xe đẹp) or Noun + Noun (trạm sạc)
            for i in range(len(doc) - 1):
                t1, t2 = doc[i], doc[i + 1]
                if t1.pos_ == "NOUN" and t2.pos_ in ["ADJ", "NOUN"]:
                    phrase = f"{t1.text} {t2.text}".strip()
                    if len(phrase) > 3:  # Filter short phrases
                        chunks.append(phrase)
        else:
            # Method 3: Fallback for blank models (no POS tagging)
            # Extract all non-stopword tokens with length > 2
            # This is less precise but works with blank models
            for token in doc:
                if not token.is_stop and not token.is_punct and len(token.text) > 2:
                    text = token.text.strip()
                    if text:
                        chunks.append(text)

        # Remove duplicates while preserving order
        seen = set()
        unique_chunks = []
        for chunk in chunks:
            chunk_lower = chunk.lower()
            if chunk_lower not in seen:
                seen.add(chunk_lower)
                unique_chunks.append(chunk)

        return unique_chunks[:20]  # Limit to top 20

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
