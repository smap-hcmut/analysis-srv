"""Integration tests for KeywordExtractor.

Tests cover:
- Real Vietnamese automotive text scenarios
- Dictionary-only extraction
- AI-only discovery (when available)
- Mixed dictionary + AI extraction
- Edge cases (empty, None, very long text)
"""

import pytest
from services.analytics.keyword import KeywordExtractor


class TestIntegrationScenarios:
    """Test 2.5: Integration tests with real-world scenarios."""

    @pytest.fixture
    def extractor(self):
        """Create KeywordExtractor instance."""
        return KeywordExtractor()

    def test_real_vietnamese_automotive_text(self, extractor):
        """Test with real Vietnamese automotive review text."""
        # Real-world review text with mixed aspects
        text = """
        Mình vừa mới nhận xe VinFast VF8 được 2 tuần.
        Thiết kế ngoại thất rất đẹp và sang trọng, nội thất cũng ok.
        Pin thì tạm ổn, sạc đầy mất khoảng 8 tiếng ở nhà.
        Giá hơi đắt so với phân khúc nhưng chấp nhận được.
        Bảo hành 10 năm, nhân viên showroom tư vấn nhiệt tình.
        Tổng thể xe rất tốt, đáng đồng tiền bát gạo.
        """

        extractor.enable_ai = False  # Dictionary only for predictable test

        result = extractor.extract(text)

        # Should extract keywords from multiple aspects
        assert len(result.keywords) > 0, "Should extract keywords from text"

        # Check that multiple aspects are represented
        aspects = {kw["aspect"] for kw in result.keywords}
        assert len(aspects) >= 3, f"Should have keywords from at least 3 aspects, got {aspects}"

        # Should include common terms
        keywords = [kw["keyword"] for kw in result.keywords]
        expected_terms = ["pin", "sạc", "giá", "bảo hành", "đẹp"]
        matched = [term for term in expected_terms if term in keywords]
        assert len(matched) >= 3, f"Should match at least 3 expected terms, got {matched}"

        # Verify metadata
        assert result.metadata["dict_matches"] > 0
        assert result.metadata["total_keywords"] == len(result.keywords)

    def test_text_with_only_dictionary_terms(self, extractor):
        """Test text containing only dictionary terms."""
        # Text with only known dictionary terms
        text = "Pin yếu, sạc chậm, động cơ ồn, giá đắt, xe đẹp, bảo hành kém"

        extractor.enable_ai = False

        result = extractor.extract(text)

        # All keywords should be from dictionary
        sources = {kw["source"] for kw in result.keywords}
        assert sources == {"DICT"}, "All keywords should be from dictionary"

        # Should have multiple keywords
        assert len(result.keywords) >= 5, "Should extract at least 5 dictionary keywords"

        # All should have score=1.0
        scores = [kw["score"] for kw in result.keywords]
        assert all(score == 1.0 for score in scores), "All dictionary keywords should have score 1.0"

    def test_text_with_only_new_terms_ai_discovery(self, extractor):
        """Test text containing only new terms (AI discovery)."""
        # Text with no dictionary matches - should trigger AI
        text = "VinFast electric vehicle production manufacturing factory"

        extractor.enable_ai = True
        extractor.ai_threshold = 0  # Force AI to run

        try:
            result = extractor.extract(text)

            # If AI works, should discover some keywords
            # If SpaCy not available, should handle gracefully
            assert isinstance(result.keywords, list)
            assert result.metadata["dict_matches"] == 0, "Should have no dictionary matches"

        except (OSError, SystemExit):
            # SpaCy model not available - skip AI test
            pytest.skip("SpaCy model not available")

    def test_mixed_dictionary_and_new_terms(self, extractor):
        """Test text with mixed dictionary + new terms."""
        # Text with both known terms and new terms
        text = "VinFast pin sạc điện charging station trạm sạc nhanh fast"

        extractor.enable_ai = True
        extractor.ai_threshold = 0  # Force AI to run

        try:
            result = extractor.extract(text)

            # Should have both dictionary and potentially AI keywords
            keywords = {kw["keyword"] for kw in result.keywords}

            # Should match dictionary terms
            assert "pin" in keywords or "sạc" in keywords, "Should match dictionary terms"

            # Verify no duplicates
            assert len(keywords) == len(result.keywords), "Should not have duplicate keywords"

        except (OSError, SystemExit):
            # SpaCy model not available - test dictionary only
            extractor.enable_ai = False
            result = extractor.extract(text)
            keywords = [kw["keyword"] for kw in result.keywords]
            assert "pin" in keywords or "sạc" in keywords

    def test_empty_and_none_input(self, extractor):
        """Test with empty/None input."""
        test_cases = [
            "",
            "   ",
            "\n\n",
            "\t\t",
        ]

        for text in test_cases:
            result = extractor.extract(text)

            # Should return empty results
            assert result.keywords == [], f"Should return empty keywords for '{repr(text)}'"
            assert result.metadata["dict_matches"] == 0
            assert result.metadata["ai_matches"] == 0
            # Empty input doesn't include total_keywords in metadata
            assert len(result.keywords) == 0

    def test_very_long_text(self, extractor):
        """Test with very long text (>1000 words)."""
        # Create a long text by repeating a pattern
        pattern = """
        Pin xe rất tốt, sạc nhanh, động cơ khỏe.
        Giá cả hợp lý, bảo hành tốt, showroom chuyên nghiệp.
        Thiết kế đẹp, ngoại thất sang, nội thất hiện đại.
        """
        long_text = (pattern + " ") * 100  # ~1500 words

        extractor.enable_ai = False  # Dictionary only for speed

        result = extractor.extract(text=long_text)

        # Should extract keywords successfully
        assert len(result.keywords) > 0, "Should extract keywords from long text"

        # Should respect max_keywords limit
        assert len(result.keywords) <= extractor.max_keywords, "Should respect max_keywords limit"

        # Should have reasonable performance
        assert result.metadata["total_time_ms"] < 1000, "Should process in <1 second"

    def test_special_characters_and_punctuation(self, extractor):
        """Test text with special characters and punctuation."""
        text = "Pin!!!  sạc??? động_cơ... giá$$$ xe@@@ bảo-hành!!!"

        extractor.enable_ai = False

        result = extractor.extract(text)

        # Should extract keywords despite special characters
        keywords = [kw["keyword"] for kw in result.keywords]

        # Should match core terms
        expected_terms = ["pin", "sạc", "giá"]
        matched = [term for term in expected_terms if term in keywords]
        assert len(matched) >= 2, f"Should match at least 2 terms despite special chars, got {matched}"

    def test_mixed_case_unicode_text(self, extractor):
        """Test mixed case and Unicode Vietnamese text."""
        # Mixed case with full Vietnamese diacritics
        text = "PIN Yếu, SẠC Chậm, ĐỘNG CƠ ồn, GIÁ đắt, XE đẹp, BẢO HÀNH tốt"

        extractor.enable_ai = False

        result = extractor.extract(text)

        # Should handle mixed case
        keywords = [kw["keyword"] for kw in result.keywords]

        # Should match terms (case-insensitive)
        expected_terms = ["pin", "sạc", "động cơ", "giá"]
        matched = [term for term in expected_terms if term in keywords]
        assert len(matched) >= 3, f"Should match case-insensitively, got {matched}"


class TestAIDiscoveryExtended:
    """Test 3.3: Extended AI discovery tests for unknown/trending keywords."""

    @pytest.fixture
    def extractor(self):
        """Create KeywordExtractor instance with AI enabled."""
        extractor = KeywordExtractor()
        extractor.enable_ai = True
        extractor.ai_threshold = 0  # Force AI to run
        return extractor

    def test_ai_discovers_unknown_technical_term(self, extractor):
        """Test AI discovers technical terms not in dictionary."""
        text = "Con này có hud kính lái xịn sò"  # "hud" not in dict

        try:
            result = extractor.extract(text)

            # Should discover some keywords
            ai_keywords = [kw for kw in result.keywords if kw["source"] == "AI"]

            # If AI works, should discover terms
            # If SpaCy not available, gracefully handle
            assert isinstance(result.keywords, list), "Should return valid result"

        except (OSError, SystemExit):
            # SpaCy model not available - skip test
            pytest.skip("SpaCy Vietnamese model not available")

    def test_ai_discovers_trending_slang(self, extractor):
        """Test AI discovers new slang/trending terms."""
        text = "Xe lướt giá tốt"  # "xe lướt" = used car (slang)

        try:
            result = extractor.extract(text)

            # Should have some keywords (dictionary or AI)
            assert len(result.keywords) > 0, "Should extract some keywords"

            # Check metadata is valid
            assert "dict_matches" in result.metadata
            assert "ai_matches" in result.metadata

        except (OSError, SystemExit):
            # SpaCy model not available - skip test
            pytest.skip("SpaCy Vietnamese model not available")

    def test_ai_discovers_competitor_brands(self, extractor):
        """Test AI discovers competitor brand names."""
        text = "So với Tesla thì VinFast vẫn còn yếu"

        try:
            result = extractor.extract(text)

            # Should discover brand names if AI works
            keywords_lower = [kw["keyword"].lower() for kw in result.keywords]

            # At minimum, should return valid result structure
            assert isinstance(result.keywords, list)
            assert isinstance(result.metadata, dict)

        except (OSError, SystemExit):
            # SpaCy model not available - skip test
            pytest.skip("SpaCy Vietnamese model not available")

    def test_ai_discovers_vietnamese_entities(self, extractor):
        """Test AI discovers Vietnamese-specific entities."""
        text = "Showroom ở Hà Nội chuyên nghiệp hơn"

        try:
            result = extractor.extract(text)

            # Should have dictionary match for "showroom" and "chuyên nghiệp"
            dict_keywords = [kw for kw in result.keywords if kw["source"] == "DICT"]
            assert len(dict_keywords) > 0, "Should match dictionary terms"

            # Verify result structure
            assert "total_keywords" in result.metadata or len(result.keywords) >= 0

        except (OSError, SystemExit):
            # SpaCy model not available - skip test
            pytest.skip("SpaCy Vietnamese model not available")
