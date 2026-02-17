import logging
import warnings
import numpy as np  # type: ignore
from typing import Dict, List
import spacy  # type: ignore
import yake  # type: ignore
from .interface import ISpacyYake
from .constant import *
from .type import SpacyYakeConfig, SpacyYakeOutput, SpacyYakeItem


class SpacyYake(ISpacyYake):
    """SpaCy + YAKE wrapper for keyword extraction.

    This class handles:
    - Named entity recognition using SpaCy
    - Noun chunk extraction using SpaCy
    - Statistical keyword extraction using YAKE
    - Keyword combination and scoring

    Attributes:
        config: SpacyYakeConfig configuration
        nlp: SpaCy model instance
        yake_extractor: YAKE extractor instance
    """

    def __init__(self, config: SpacyYakeConfig):
        """Initialize SpaCy and YAKE extractors.

        Args:
            config: SpacyYakeConfig configuration

        Raises:
            ImportError: If spaCy or YAKE libraries are not installed
            OSError: If SpaCy model is not found
        """
        self.config = config
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
        fallback_models = [config.spacy_model]

        # If user specified Vietnamese model, add fallbacks
        if "vi_core" in config.spacy_model:
            # Try smaller Vietnamese model if large fails
            if "_lg" in config.spacy_model:
                fallback_models.append(config.spacy_model.replace("_lg", "_sm"))
            elif "_sm" in config.spacy_model:
                fallback_models.append(config.spacy_model.replace("_sm", "_lg"))

        # Always try multilingual model (official, stable)
        if SpacyModel.XX_ENT_WIKI_SM not in fallback_models:
            fallback_models.append(SpacyModel.XX_ENT_WIKI_SM.value)

        # Try English model as additional fallback
        if SpacyModel.EN_CORE_WEB_SM not in fallback_models:
            fallback_models.append(SpacyModel.EN_CORE_WEB_SM.value)

        # Try to load from fallback chain
        for model_name in fallback_models:
            try:
                # Suppress spacy model version warning
                with warnings.catch_warnings():
                    warnings.filterwarnings("ignore", category=UserWarning, module="spacy")
                    self.nlp = spacy.load(model_name)
                self.logger.info(f"Loaded SpaCy model: {model_name}")
                model_loaded = True
                break
            except OSError:
                continue

        # Final fallback: Blank Vietnamese model (tokenizer only)
        if not model_loaded:
            try:
                self.logger.warning(
                    f" No pre-trained model found. Using blank 'vi' model (tokenizer only).\n"
                    f"Attempted models: {', '.join(fallback_models)}\n"
                    f"To improve AI Discovery, install multilingual model:\n"
                    f"  uv run python -m spacy download xx_ent_wiki_sm"
                )
                self.nlp = spacy.blank(SpacyModel.BLANK_VI.value)
                # Blank model needs sentencizer for sentence segmentation
                if "sentencizer" not in self.nlp.pipe_names:
                    self.nlp.add_pipe("sentencizer")
                self.logger.info("Using blank Vietnamese model with sentencizer")
            except Exception as e:
                self.logger.error(f"Failed to create blank model: {e}")
                self.nlp = None

        # Initialize YAKE
        if yake is None:
            self.logger.error("Failed to import YAKE")
            self.yake_extractor = None
            raise ImportError("yake is not installed")

        yake_config = {
            "lan": config.yake_language,
            "n": config.yake_n,
            "dedupLim": config.yake_dedup_lim,
            "top": config.yake_max_keywords,
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
        if len(text) > MAX_TEXT_LENGTH_WARNING:
            self.logger.warning(
                f"Text length {len(text)} exceeds recommended limit of {MAX_TEXT_LENGTH_WARNING}"
            )
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
            if (
                len(ent.text.split()) <= ENTITY_MAX_WORDS
                and len(ent.text.strip()) > ENTITY_MIN_LENGTH
                and not ent.text.isdigit()
            ):
                entities.append((ent.text.strip(), ent.label_))
        return entities[:MAX_ENTITIES_RETURN]

    def _extract_noun_chunks(self, doc) -> List[str]:
        """Extract and filter noun chunks using POS tagging.

        Args:
            doc: SpaCy Doc object

        Returns:
            List of noun chunk strings
        """
        chunks = []

        # Check if model has POS tagging capability
        has_pos_tagging = any(
            hasattr(token, "pos_") and token.pos_
            for token in doc
            if hasattr(token, "pos_")
        )

        # Method 1: Use built-in noun chunks if available (full models)
        if doc.has_annotation("DEP"):
            try:
                for chunk in doc.noun_chunks:
                    text = chunk.text.strip()
                    if len(text) > MIN_NOUN_CHUNK_LENGTH:
                        chunks.append(text)
            except (AttributeError, KeyError):
                # Some models don't support noun_chunks
                pass

        # Method 2: Extract based on POS tags (if model has POS tagging)
        if has_pos_tagging:
            # Extract single nouns and proper nouns
            for token in doc:
                if (
                    token.pos_ in [POSTag.NOUN.value, POSTag.PROPN.value]
                    and not token.is_stop
                    and not token.is_punct
                ):
                    text = token.text.strip()
                    if len(text) > 1:  # Filter out single characters
                        chunks.append(text)

            # Extract simple noun phrases (Noun + Adj, Noun + Noun)
            for i in range(len(doc) - 1):
                t1, t2 = doc[i], doc[i + 1]
                if t1.pos_ == POSTag.NOUN.value and t2.pos_ in [
                    POSTag.ADJ.value,
                    POSTag.NOUN.value,
                ]:
                    phrase = f"{t1.text} {t2.text}".strip()
                    if len(phrase) > MIN_NOUN_PHRASE_LENGTH:
                        chunks.append(phrase)
        else:
            # Method 3: Fallback for blank models (no POS tagging)
            for token in doc:
                if (
                    not token.is_stop
                    and not token.is_punct
                    and len(token.text) > MIN_TOKEN_LENGTH_BLANK
                ):
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

        return unique_chunks[:MAX_NOUN_CHUNKS_RETURN]

    def _combine_keyword_sources(
        self, yake_keywords: List[tuple], entities: List[tuple], noun_chunks: List[str]
    ) -> List[SpacyYakeItem]:
        """Combine keywords from different sources with appropriate scoring.

        Args:
            yake_keywords: List of (keyword, score) from YAKE
            entities: List of (entity, label) from SpaCy
            noun_chunks: List of noun chunks from SpaCy

        Returns:
            Combined and sorted list of SpacyYakeItem
        """
        keywords: List[SpacyYakeItem] = []

        # Add YAKE keywords (statistical)
        for i, (keyword, score) in enumerate(yake_keywords):
            keywords.append(
                SpacyYakeItem(
                    keyword=keyword.strip(),
                    score=SCORE_MAX_LIMIT - score,  # YAKE: lower is better, so invert
                    rank=i + 1,
                    type=KeywordType.STATISTICAL.value,
                    relevance=SCORE_MAX_LIMIT - score,
                )
            )

        # Add named entities (linguistic)
        for entity, label in entities:
            keywords.append(
                SpacyYakeItem(
                    keyword=entity,
                    score=self.config.entity_weight,
                    rank=len(keywords) + 1,
                    type=f"{KeywordType.ENTITY.value}_{label.lower()}",
                    relevance=self.config.entity_weight,
                )
            )

        # Add noun chunks (syntactic)
        for chunk in noun_chunks:
            keywords.append(
                SpacyYakeItem(
                    keyword=chunk,
                    score=self.config.chunk_weight,
                    rank=len(keywords) + 1,
                    type=KeywordType.SYNTACTIC.value,
                    relevance=self.config.chunk_weight,
                )
            )

        # Sort by score descending
        keywords.sort(key=lambda x: x.score, reverse=True)

        # Re-rank after sorting
        for i, kw in enumerate(keywords):
            kw.rank = i + 1

        return keywords

    def _calculate_confidence(
        self,
        keywords: List[SpacyYakeItem],
        entities: List[tuple],
        noun_chunks: List[str],
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
        keyword_count_score = min(len(keywords) / KEYWORD_COUNT_DIVISOR, 1.0)

        # Diversity bonus from different source types
        source_types = set(kw.type for kw in keywords)
        diversity_bonus = min(
            len(source_types) / DIVERSITY_DIVISOR, DIVERSITY_BONUS_MAX
        )

        # Entity quality bonus
        entity_types = set(label for _, label in entities) if entities else set()
        entity_bonus = min(len(entity_types) / ENTITY_TYPES_DIVISOR, ENTITY_BONUS_MAX)

        # Score distribution quality
        scores = [kw.score for kw in keywords]
        score_variance = np.var(scores) if len(scores) > 1 else 0
        variance_bonus = min(score_variance, VARIANCE_BONUS_MAX)

        # Combine all factors
        confidence = (
            keyword_count_score + diversity_bonus + entity_bonus + variance_bonus
        )
        return min(confidence, 1.0)

    def extract(self, text: str) -> SpacyYakeOutput:
        """Extract keywords from text.

        Args:
            text: Input text to extract keywords from

        Returns:
            SpacyYakeOutput with keywords and metadata
        """
        # Validate input
        if not self._validate_text(text):
            return SpacyYakeOutput(
                success=False,
                error_message=ERROR_INVALID_INPUT,
                metadata={"error": ERROR_INVALID_INPUT},
                confidence_score=0.0,
            )

        # Check if models are loaded
        if not self.nlp or not self.yake_extractor:
            return SpacyYakeOutput(
                success=False,
                error_message=ERROR_MODEL_NOT_INITIALIZED,
                metadata={"error": ERROR_MODEL_NOT_INITIALIZED},
                confidence_score=0.0,
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
            keywords = self._combine_keyword_sources(
                yake_keywords, entities, noun_chunks
            )

            # Calculate confidence score
            confidence = self._calculate_confidence(keywords, entities, noun_chunks)

            # Limit results based on configuration
            final_keywords = keywords[: self.config.max_keywords]

            # Build metadata (kept as dict for flexibility, but could be strictly typed too)
            metadata = {
                "method": "spacy_yake",
                "entities_count": len(entities),
                "noun_chunks_count": len(noun_chunks),
                "yake_keywords_count": len(yake_keywords),
                "total_candidates": len(keywords),
                "final_count": len(final_keywords),
            }

            return SpacyYakeOutput(
                keywords=final_keywords,
                metadata=metadata,
                confidence_score=confidence,
                success=True,
            )

        except Exception as e:
            self.logger.error(f"Error during extraction: {str(e)}")
            return SpacyYakeOutput(
                success=False,
                error_message=str(e),
                metadata={"error": str(e)},
                confidence_score=0.0,
            )

    def extract_batch(self, texts: List[str]) -> List[SpacyYakeOutput]:
        """Extract keywords from multiple texts.

        Args:
            texts: List of input texts

        Returns:
            List of SpacyYakeOutput objects
        """
        return [self.extract(text) for text in texts]
