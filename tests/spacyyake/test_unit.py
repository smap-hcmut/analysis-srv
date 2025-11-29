"""Comprehensive unit tests for SpaCy-YAKE keyword extraction."""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import pytest  # type: ignore
import numpy as np  # type: ignore
from unittest.mock import Mock, patch, MagicMock

from infrastructure.ai.spacyyake_extractor import SpacyYakeExtractor, ExtractionResult
from infrastructure.ai.aspect_mapper import AspectMapper


class TestSpacyYakeExtractorInitialization:
    """Test SpacyYakeExtractor initialization."""

    def test_initialization_with_defaults(self):
        """Test initialization with default parameters."""
        with (
            patch("infrastructure.ai.spacyyake_extractor.spacy") as mock_spacy,
            patch("infrastructure.ai.spacyyake_extractor.yake"),
        ):
            mock_spacy.load.return_value = MagicMock()

            extractor = SpacyYakeExtractor()

            assert extractor.spacy_model == "en_core_web_sm"
            assert extractor.max_keywords == 30
            assert extractor.entity_weight == 0.7
            assert extractor.chunk_weight == 0.5
            mock_spacy.load.assert_called_once_with("en_core_web_sm")

    def test_initialization_with_custom_params(self):
        """Test initialization with custom parameters."""
        with (
            patch("infrastructure.ai.spacyyake_extractor.spacy") as mock_spacy,
            patch("infrastructure.ai.spacyyake_extractor.yake"),
        ):
            mock_spacy.load.return_value = MagicMock()

            extractor = SpacyYakeExtractor(
                spacy_model="en_core_web_md", max_keywords=50, entity_weight=0.8, chunk_weight=0.6
            )

            assert extractor.spacy_model == "en_core_web_md"
            assert extractor.max_keywords == 50
            assert extractor.entity_weight == 0.8
            assert extractor.chunk_weight == 0.6
            mock_spacy.load.assert_called_once_with("en_core_web_md")

    def test_initialization_downloads_missing_model(self):
        """Test that missing SpaCy model is downloaded."""
        with (
            patch("infrastructure.ai.spacyyake_extractor.spacy") as mock_spacy,
            patch("infrastructure.ai.spacyyake_extractor.yake"),
        ):
            # First call raises OSError, second succeeds
            mock_spacy.load.side_effect = [OSError("Model not found"), MagicMock()]

            extractor = SpacyYakeExtractor()

            assert mock_spacy.load.call_count == 2
            mock_spacy.cli.download.assert_called_once_with("en_core_web_sm")

    def test_initialization_handles_import_error(self):
        """Test handling of missing spaCy library."""
        with patch("infrastructure.ai.spacyyake_extractor.spacy") as mock_spacy:
            mock_spacy.load.side_effect = ImportError("spaCy not installed")

            with pytest.raises(ImportError):
                SpacyYakeExtractor()


class TestTextValidation:
    """Test text validation functionality."""

    @pytest.fixture
    def extractor(self):
        """Create a mock extractor for testing."""
        with (
            patch("infrastructure.ai.spacyyake_extractor.spacy") as mock_spacy,
            patch("infrastructure.ai.spacyyake_extractor.yake"),
        ):
            mock_spacy.load.return_value = MagicMock()
            return SpacyYakeExtractor()

    def test_validate_valid_text(self, extractor):
        """Test validation with valid text."""
        assert extractor._validate_text("This is a valid text")
        assert extractor._validate_text("Hello world!")

    def test_validate_empty_text(self, extractor):
        """Test validation with empty text."""
        assert not extractor._validate_text("")
        assert not extractor._validate_text("   ")
        assert not extractor._validate_text("\n\t")

    def test_validate_non_string(self, extractor):
        """Test validation with non-string input."""
        assert not extractor._validate_text(None)
        assert not extractor._validate_text(123)
        assert not extractor._validate_text(["text"])

    def test_validate_long_text(self, extractor):
        """Test validation with very long text (should warn but return True)."""
        long_text = "a" * 15000
        assert extractor._validate_text(long_text)


class TestEntityExtraction:
    """Test named entity extraction."""

    @pytest.fixture
    def extractor(self):
        """Create a mock extractor for testing."""
        with (
            patch("infrastructure.ai.spacyyake_extractor.spacy") as mock_spacy,
            patch("infrastructure.ai.spacyyake_extractor.yake"),
        ):
            mock_spacy.load.return_value = MagicMock()
            return SpacyYakeExtractor()

    def test_extract_entities_basic(self, extractor):
        """Test basic entity extraction."""
        # Create mock entities
        mock_ent1 = MagicMock()
        mock_ent1.text = "Apple Inc"
        mock_ent1.label_ = "ORG"

        mock_ent2 = MagicMock()
        mock_ent2.text = "California"
        mock_ent2.label_ = "GPE"

        mock_doc = MagicMock()
        mock_doc.ents = [mock_ent1, mock_ent2]

        entities = extractor._extract_entities(mock_doc)

        assert len(entities) == 2
        assert ("Apple Inc", "ORG") in entities
        assert ("California", "GPE") in entities

    def test_extract_entities_filter_long_entities(self, extractor):
        """Test filtering of entities with too many words."""
        mock_ent = MagicMock()
        mock_ent.text = "This is a very long entity name with many words"
        mock_ent.label_ = "ORG"

        mock_doc = MagicMock()
        mock_doc.ents = [mock_ent]

        entities = extractor._extract_entities(mock_doc)

        # Should be filtered out (more than 3 words)
        assert len(entities) == 0

    def test_extract_entities_filter_digits(self, extractor):
        """Test filtering of numeric entities."""
        mock_ent = MagicMock()
        mock_ent.text = "12345"
        mock_ent.label_ = "CARDINAL"

        mock_doc = MagicMock()
        mock_doc.ents = [mock_ent]

        entities = extractor._extract_entities(mock_doc)

        # Should be filtered out (all digits)
        assert len(entities) == 0

    def test_extract_entities_limit_to_15(self, extractor):
        """Test that only top 15 entities are returned."""
        mock_ents = []
        for i in range(20):
            mock_ent = MagicMock()
            mock_ent.text = f"Entity{i}"
            mock_ent.label_ = "ORG"
            mock_ents.append(mock_ent)

        mock_doc = MagicMock()
        mock_doc.ents = mock_ents

        entities = extractor._extract_entities(mock_doc)

        assert len(entities) == 15


class TestNounChunkExtraction:
    """Test noun chunk extraction."""

    @pytest.fixture
    def extractor(self):
        """Create a mock extractor for testing."""
        with (
            patch("infrastructure.ai.spacyyake_extractor.spacy") as mock_spacy,
            patch("infrastructure.ai.spacyyake_extractor.yake"),
        ):
            mock_spacy.load.return_value = MagicMock()
            return SpacyYakeExtractor()

    def test_extract_noun_chunks_basic(self, extractor):
        """Test basic noun chunk extraction."""
        mock_chunk1 = MagicMock()
        mock_chunk1.text = "great product"

        mock_chunk2 = MagicMock()
        mock_chunk2.text = "excellent quality"

        mock_doc = MagicMock()
        mock_doc.noun_chunks = [mock_chunk1, mock_chunk2]

        chunks = extractor._extract_noun_chunks(mock_doc)

        assert len(chunks) == 2
        assert "great product" in chunks
        assert "excellent quality" in chunks

    def test_extract_noun_chunks_filter_single_word(self, extractor):
        """Test filtering of single-word chunks."""
        mock_chunk = MagicMock()
        mock_chunk.text = "product"

        mock_doc = MagicMock()
        mock_doc.noun_chunks = [mock_chunk]

        chunks = extractor._extract_noun_chunks(mock_doc)

        # Should be filtered out (only 1 word)
        assert len(chunks) == 0

    def test_extract_noun_chunks_filter_too_long(self, extractor):
        """Test filtering of chunks with too many words."""
        mock_chunk = MagicMock()
        mock_chunk.text = "the very long noun chunk phrase"

        mock_doc = MagicMock()
        mock_doc.noun_chunks = [mock_chunk]

        chunks = extractor._extract_noun_chunks(mock_doc)

        # Should be filtered out (more than 4 words)
        assert len(chunks) == 0

    def test_extract_noun_chunks_filter_short_text(self, extractor):
        """Test filtering of very short chunks."""
        mock_chunk = MagicMock()
        mock_chunk.text = "ab"

        mock_doc = MagicMock()
        mock_doc.noun_chunks = [mock_chunk]

        chunks = extractor._extract_noun_chunks(mock_doc)

        # Should be filtered out (less than 4 chars)
        assert len(chunks) == 0

    def test_extract_noun_chunks_limit_to_20(self, extractor):
        """Test that only top 20 chunks are returned."""
        mock_chunks = []
        for i in range(30):
            mock_chunk = MagicMock()
            mock_chunk.text = f"chunk number {i}"
            mock_chunks.append(mock_chunk)

        mock_doc = MagicMock()
        mock_doc.noun_chunks = mock_chunks

        chunks = extractor._extract_noun_chunks(mock_doc)

        assert len(chunks) == 20


class TestKeywordCombination:
    """Test keyword combination logic."""

    @pytest.fixture
    def extractor(self):
        """Create a mock extractor for testing."""
        with (
            patch("infrastructure.ai.spacyyake_extractor.spacy") as mock_spacy,
            patch("infrastructure.ai.spacyyake_extractor.yake"),
        ):
            mock_spacy.load.return_value = MagicMock()
            return SpacyYakeExtractor()

    def test_combine_keyword_sources_basic(self, extractor):
        """Test basic keyword combination."""
        yake_keywords = [("machine learning", 0.1), ("data science", 0.2)]
        entities = [("Google", "ORG")]
        noun_chunks = ["big data"]

        keywords = extractor._combine_keyword_sources(yake_keywords, entities, noun_chunks)

        # Should have 4 keywords total
        assert len(keywords) == 4

        # Check YAKE keywords (scores should be inverted)
        yake_kw = [k for k in keywords if k["type"] == "statistical"]
        assert len(yake_kw) == 2
        assert yake_kw[0]["keyword"] == "machine learning"
        assert yake_kw[0]["score"] == 0.9  # 1.0 - 0.1

    def test_combine_keyword_sources_sorting(self, extractor):
        """Test that combined keywords are sorted by score."""
        yake_keywords = [
            ("keyword1", 0.5),
            ("keyword2", 0.1),
        ]  # keyword2 will have higher score (0.9)
        entities = []
        noun_chunks = []

        keywords = extractor._combine_keyword_sources(yake_keywords, entities, noun_chunks)

        # Should be sorted by score descending
        assert keywords[0]["keyword"] == "keyword2"
        assert keywords[0]["score"] == 0.9
        assert keywords[1]["keyword"] == "keyword1"
        assert keywords[1]["score"] == 0.5

    def test_combine_keyword_sources_ranking(self, extractor):
        """Test that ranks are assigned correctly after sorting."""
        yake_keywords = [("kw1", 0.3), ("kw2", 0.1)]
        entities = []
        noun_chunks = []

        keywords = extractor._combine_keyword_sources(yake_keywords, entities, noun_chunks)

        assert keywords[0]["rank"] == 1
        assert keywords[1]["rank"] == 2

    def test_combine_keyword_sources_entity_weight(self, extractor):
        """Test that entity weights are applied correctly."""
        yake_keywords = []
        entities = [("Apple", "ORG")]
        noun_chunks = []

        keywords = extractor._combine_keyword_sources(yake_keywords, entities, noun_chunks)

        assert len(keywords) == 1
        assert keywords[0]["score"] == extractor.entity_weight
        assert keywords[0]["type"] == "entity_org"

    def test_combine_keyword_sources_chunk_weight(self, extractor):
        """Test that chunk weights are applied correctly."""
        yake_keywords = []
        entities = []
        noun_chunks = ["great product"]

        keywords = extractor._combine_keyword_sources(yake_keywords, entities, noun_chunks)

        assert len(keywords) == 1
        assert keywords[0]["score"] == extractor.chunk_weight
        assert keywords[0]["type"] == "syntactic"


class TestConfidenceCalculation:
    """Test confidence score calculation."""

    @pytest.fixture
    def extractor(self):
        """Create a mock extractor for testing."""
        with (
            patch("infrastructure.ai.spacyyake_extractor.spacy") as mock_spacy,
            patch("infrastructure.ai.spacyyake_extractor.yake"),
        ):
            mock_spacy.load.return_value = MagicMock()
            return SpacyYakeExtractor()

    def test_calculate_confidence_empty_keywords(self, extractor):
        """Test confidence calculation with no keywords."""
        confidence = extractor._calculate_confidence([], [], [])
        assert confidence == 0.0

    def test_calculate_confidence_basic(self, extractor):
        """Test basic confidence calculation."""
        keywords = [
            {"type": "statistical", "score": 0.9},
            {"type": "entity_org", "score": 0.7},
        ]
        entities = [("Entity1", "ORG")]
        noun_chunks = ["chunk1"]

        confidence = extractor._calculate_confidence(keywords, entities, noun_chunks)

        # Should be between 0 and 1
        assert 0.0 <= confidence <= 1.0

    def test_calculate_confidence_diversity_bonus(self, extractor):
        """Test that diversity bonus increases confidence."""
        keywords_low_diversity = [
            {"type": "statistical", "score": 0.9},
            {"type": "statistical", "score": 0.8},
        ]

        keywords_high_diversity = [
            {"type": "statistical", "score": 0.9},
            {"type": "entity_org", "score": 0.7},
            {"type": "syntactic", "score": 0.6},
        ]

        conf_low = extractor._calculate_confidence(keywords_low_diversity, [], [])
        conf_high = extractor._calculate_confidence(
            keywords_high_diversity, [("E", "ORG")], ["chunk"]
        )

        # Higher diversity should give higher confidence
        assert conf_high > conf_low

    def test_calculate_confidence_capped_at_1(self, extractor):
        """Test that confidence is capped at 1.0."""
        # Create many keywords to potentially exceed 1.0
        keywords = [{"type": f"type{i}", "score": 0.9} for i in range(50)]
        entities = [(f"E{i}", "ORG") for i in range(10)]
        noun_chunks = [f"chunk{i}" for i in range(20)]

        confidence = extractor._calculate_confidence(keywords, entities, noun_chunks)

        assert confidence <= 1.0


class TestExtraction:
    """Test main extraction functionality."""

    @pytest.fixture
    def extractor(self):
        """Create a mock extractor for testing."""
        with (
            patch("infrastructure.ai.spacyyake_extractor.spacy") as mock_spacy,
            patch("infrastructure.ai.spacyyake_extractor.yake") as mock_yake,
        ):
            mock_nlp = MagicMock()
            mock_spacy.load.return_value = mock_nlp

            mock_yake_extractor = MagicMock()
            mock_yake.KeywordExtractor.return_value = mock_yake_extractor

            ext = SpacyYakeExtractor()
            return ext

    def test_extract_invalid_text(self, extractor):
        """Test extraction with invalid text."""
        result = extractor.extract("")

        assert not result.success
        assert result.error_message == "Invalid input text"

    def test_extract_models_not_initialized(self):
        """Test extraction when models are not initialized."""
        with (
            patch("infrastructure.ai.spacyyake_extractor.spacy") as mock_spacy,
            patch("infrastructure.ai.spacyyake_extractor.yake"),
        ):
            mock_spacy.load.return_value = MagicMock()
            extractor = SpacyYakeExtractor()
            extractor.nlp = None  # Simulate failed initialization

            result = extractor.extract("Test text")

            assert not result.success
            assert "not initialized" in result.error_message.lower()

    def test_extract_success(self, extractor):
        """Test successful extraction."""
        # Mock SpaCy doc
        mock_doc = MagicMock()
        mock_doc.ents = []
        mock_doc.noun_chunks = []
        extractor.nlp.return_value = mock_doc

        # Mock YAKE results
        extractor.yake_extractor.extract_keywords.return_value = [
            ("keyword1", 0.1),
            ("keyword2", 0.2),
        ]

        result = extractor.extract("This is a test text")

        assert result.success
        assert len(result.keywords) > 0
        assert result.confidence_score >= 0.0
        assert "method" in result.metadata

    def test_extract_respects_max_keywords(self, extractor):
        """Test that max_keywords limit is respected."""
        extractor.max_keywords = 5

        # Mock SpaCy doc
        mock_doc = MagicMock()
        mock_doc.ents = []
        mock_doc.noun_chunks = []
        extractor.nlp.return_value = mock_doc

        # Mock YAKE with many keywords
        extractor.yake_extractor.extract_keywords.return_value = [
            (f"keyword{i}", 0.1 * i) for i in range(20)
        ]

        result = extractor.extract("Test text")

        assert result.success
        assert len(result.keywords) <= 5

    def test_extract_batch(self, extractor):
        """Test batch extraction."""
        # Mock SpaCy doc
        mock_doc = MagicMock()
        mock_doc.ents = []
        mock_doc.noun_chunks = []
        extractor.nlp.return_value = mock_doc

        # Mock YAKE results
        extractor.yake_extractor.extract_keywords.return_value = [("keyword", 0.1)]

        texts = ["Text 1", "Text 2", "Text 3"]
        results = extractor.extract_batch(texts)

        assert len(results) == 3
        assert all(isinstance(r, ExtractionResult) for r in results)
        assert all(r.success for r in results)


class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.fixture
    def extractor(self):
        """Create a mock extractor for testing."""
        with (
            patch("infrastructure.ai.spacyyake_extractor.spacy") as mock_spacy,
            patch("infrastructure.ai.spacyyake_extractor.yake"),
        ):
            mock_spacy.load.return_value = MagicMock()
            return SpacyYakeExtractor()

    def test_extract_special_characters(self, extractor):
        """Test extraction with special characters."""
        # Mock components
        mock_doc = MagicMock()
        mock_doc.ents = []
        mock_doc.noun_chunks = []
        extractor.nlp.return_value = mock_doc
        extractor.yake_extractor.extract_keywords.return_value = []

        result = extractor.extract("Test!!! @#$ %^& ***")

        # Should still succeed even with special characters
        assert result.success

    def test_extract_unicode_text(self, extractor):
        """Test extraction with Unicode characters."""
        mock_doc = MagicMock()
        mock_doc.ents = []
        mock_doc.noun_chunks = []
        extractor.nlp.return_value = mock_doc
        extractor.yake_extractor.extract_keywords.return_value = []

        result = extractor.extract("Café résumé naïve 中文 日本語")

        assert result.success

    def test_extract_exception_handling(self, extractor):
        """Test that exceptions during extraction are handled gracefully."""
        extractor.nlp.side_effect = Exception("Processing error")

        result = extractor.extract("Test text")

        assert not result.success
        assert "Processing error" in result.error_message


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
