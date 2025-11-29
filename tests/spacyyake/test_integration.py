"""Integration tests for SpaCy-YAKE keyword extraction (requires actual models)."""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import pytest
import tempfile
import yaml

from infrastructure.ai.spacyyake_extractor import SpacyYakeExtractor
from infrastructure.ai.aspect_mapper import AspectMapper


def check_spacy_model_available():
    """Check if SpaCy model is available."""
    try:
        import spacy
        try:
            spacy.load("en_core_web_sm")
            return True
        except OSError:
            return False
    except ImportError:
        return False


def check_yake_available():
    """Check if YAKE is available."""
    try:
        import yake
        return True
    except ImportError:
        return False


@pytest.mark.skipif(
    not (check_spacy_model_available() and check_yake_available()),
    reason="SpaCy model or YAKE not available. Run 'make download-spacy-model' first.",
)
class TestRealModelExtraction:
    """Integration tests with real SpaCy and YAKE models."""

    @pytest.fixture(scope="class")
    def extractor(self):
        """Create real extractor instance once for all tests."""
        return SpacyYakeExtractor()

    def test_extract_english_text_basic(self, extractor):
        """Test extraction with basic English text."""
        text = "Machine learning is a powerful technology for data science applications."
        result = extractor.extract(text)

        assert result.success
        assert len(result.keywords) > 0
        assert result.confidence_score > 0.0

        # Check that we got diverse keyword types
        keyword_types = set(kw['type'] for kw in result.keywords)
        assert len(keyword_types) > 0

        # Verify metadata
        assert 'method' in result.metadata
        assert result.metadata['method'] == 'spacy_yake'

    def test_extract_english_text_technical(self, extractor):
        """Test extraction with technical English text."""
        text = """
        Python is a versatile programming language widely used in web development,
        data analysis, artificial intelligence, and scientific computing.
        Its simple syntax makes it ideal for beginners while remaining powerful
        for advanced applications.
        """
        result = extractor.extract(text)

        assert result.success
        assert len(result.keywords) >= 5

        # Check for expected keywords
        keywords_text = [kw['keyword'].lower() for kw in result.keywords]
        # At least one of these should be extracted
        expected_terms = ['python', 'programming', 'language', 'data', 'artificial intelligence']
        assert any(any(term in kw for term in expected_terms) for kw in keywords_text)

    def test_extract_with_named_entities(self, extractor):
        """Test extraction with text containing named entities."""
        text = "Apple Inc. released the iPhone in California. Google and Microsoft are competitors."
        result = extractor.extract(text)

        assert result.success
        assert len(result.keywords) > 0

        # Should have entity-type keywords
        entity_keywords = [kw for kw in result.keywords if 'entity' in kw['type']]
        assert len(entity_keywords) > 0

        # Check metadata
        assert result.metadata['entities_count'] > 0

    def test_extract_short_text(self, extractor):
        """Test extraction with short text."""
        text = "Great product with excellent quality!"
        result = extractor.extract(text)

        assert result.success
        # Even short text should produce some keywords
        assert len(result.keywords) >= 1

    def test_extract_long_text(self, extractor):
        """Test extraction with long text."""
        text = """
        Artificial intelligence and machine learning have revolutionized the technology industry.
        Deep learning models, powered by neural networks, can process vast amounts of data
        to identify patterns and make predictions. Natural language processing enables computers
        to understand human language. Computer vision allows machines to interpret visual information.
        These technologies are transforming healthcare, finance, transportation, and many other sectors.
        Companies invest billions in AI research and development. Ethical considerations around AI
        include privacy, bias, and job displacement. The future of AI holds both promise and challenges.
        """
        result = extractor.extract(text)

        assert result.success
        assert len(result.keywords) > 10

        # Long text should have good diversity
        keyword_types = set(kw['type'] for kw in result.keywords)
        assert len(keyword_types) >= 2

        # Should respect max_keywords limit
        assert len(result.keywords) <= extractor.max_keywords

    def test_batch_processing_real(self, extractor):
        """Test batch processing with real models."""
        texts = [
            "Machine learning is transforming data science.",
            "Python is a popular programming language.",
            "Cloud computing enables scalable infrastructure.",
        ]

        results = extractor.extract_batch(texts)

        assert len(results) == 3
        assert all(r.success for r in results)
        assert all(len(r.keywords) > 0 for r in results)
        assert all(r.confidence_score > 0.0 for r in results)

    def test_empty_text_handling(self, extractor):
        """Test handling of empty text."""
        result = extractor.extract("")

        assert not result.success
        assert "Invalid input" in result.error_message

    def test_special_characters_handling(self, extractor):
        """Test handling of special characters."""
        text = "Email: test@example.com | Price: $99.99 | Rating: 5/5 ⭐⭐⭐"
        result = extractor.extract(text)

        # Should handle special characters gracefully
        assert result.success

    def test_unicode_text_handling(self, extractor):
        """Test handling of Unicode characters."""
        text = "Café résumé naïve über München 日本語 中文"
        result = extractor.extract(text)

        # Should handle Unicode gracefully
        assert result.success

    def test_mixed_case_text(self, extractor):
        """Test extraction with mixed case text."""
        text = "MACHINE LEARNING and data SCIENCE are IMPORTANT technologies."
        result = extractor.extract(text)

        assert result.success
        assert len(result.keywords) > 0


@pytest.mark.skipif(
    not (check_spacy_model_available() and check_yake_available()),
    reason="SpaCy model or YAKE not available.",
)
class TestAspectMappingIntegration:
    """Integration tests for aspect mapping functionality."""

    @pytest.fixture
    def sample_dictionary(self):
        """Create a sample aspect dictionary."""
        return {
            'aspects': {
                'TECHNOLOGY': {
                    'keywords': ['python', 'machine learning', 'data science', 'programming']
                },
                'BUSINESS': {
                    'keywords': ['revenue', 'profit', 'investment', 'market']
                },
                'QUALITY': {
                    'keywords': ['excellent', 'great', 'quality', 'good']
                }
            }
        }

    def test_extraction_with_aspect_mapping(self, sample_dictionary):
        """Test extraction with aspect mapping enabled."""
        # Create temporary dictionary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(sample_dictionary, f)
            dict_path = f.name

        try:
            # Create aspect mapper
            mapper = AspectMapper(dictionary_path=dict_path)

            # Create extractor (without aspect mapping in extractor itself)
            extractor = SpacyYakeExtractor()

            text = "Python is a great programming language for machine learning and data science."
            result = extractor.extract(text)

            assert result.success

            # Manually map keywords to aspects
            for keyword in result.keywords:
                aspect = mapper.map_keyword(keyword['keyword'])
                # Aspect should be either known or UNKNOWN
                assert isinstance(aspect, str)

        finally:
            # Cleanup
            Path(dict_path).unlink(missing_ok=True)

    def test_aspect_statistics(self, sample_dictionary):
        """Test aspect statistics from mapped keywords."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(sample_dictionary, f)
            dict_path = f.name

        try:
            mapper = AspectMapper(dictionary_path=dict_path)
            extractor = SpacyYakeExtractor()

            text = "Python programming requires good quality code and investment in learning."
            result = extractor.extract(text)

            # Map keywords
            aspect_counts = {}
            for keyword in result.keywords:
                aspect = mapper.map_keyword(keyword['keyword'])
                aspect_counts[aspect] = aspect_counts.get(aspect, 0) + 1

            # Should have mapped some keywords
            assert len(aspect_counts) > 0

        finally:
            Path(dict_path).unlink(missing_ok=True)


@pytest.mark.skipif(
    not check_spacy_model_available(),
    reason="SpaCy model not available.",
)
class TestModelConfiguration:
    """Test different model configurations."""

    def test_custom_max_keywords(self):
        """Test extraction with custom max keywords limit."""
        extractor = SpacyYakeExtractor(max_keywords=5)

        text = """
        Machine learning, artificial intelligence, data science, neural networks,
        deep learning, computer vision, natural language processing, and robotics
        are all important technologies in modern computing.
        """
        result = extractor.extract(text)

        assert result.success
        assert len(result.keywords) <= 5

    def test_custom_weights(self):
        """Test extraction with custom entity and chunk weights."""
        extractor = SpacyYakeExtractor(entity_weight=0.9, chunk_weight=0.3)

        text = "Apple Inc. develops innovative technology products in California."
        result = extractor.extract(text)

        assert result.success
        assert len(result.keywords) > 0

        # Verify weights are applied
        assert extractor.entity_weight == 0.9
        assert extractor.chunk_weight == 0.3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
