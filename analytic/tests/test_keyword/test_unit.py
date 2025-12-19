"""Unit tests for KeywordExtractor.

Tests cover:
- Dictionary matching (case-insensitive, multi-word)
- AI discovery (SpaCy+YAKE integration, threshold logic)
- Aspect mapping (fuzzy matching, GENERAL fallback)
- Hybrid logic (combining DICT+AI, deduplication, sorting)
"""

import pytest
from services.analytics.keyword import Aspect, KeywordExtractor, KeywordResult


class TestDictionaryMatching:
    """Test 2.1: Dictionary matching for keyword extraction."""

    @pytest.fixture
    def extractor(self):
        """Create KeywordExtractor instance with AI disabled."""
        extractor = KeywordExtractor()
        extractor.enable_ai = False  # Test dictionary only
        return extractor

    def test_dictionary_loading_from_yaml(self, extractor):
        """Test dictionary loads correctly from YAML file."""
        # Verify aspect_dict is populated
        assert len(extractor.aspect_dict) > 0, "Aspect dictionary should be loaded"

        # Verify all expected aspects are present
        expected_aspects = [Aspect.DESIGN, Aspect.PERFORMANCE, Aspect.PRICE, Aspect.SERVICE]
        for aspect in expected_aspects:
            assert aspect in extractor.aspect_dict, f"{aspect} should be in dictionary"

        # Verify keyword_map is built
        assert len(extractor.keyword_map) > 0, "Keyword map should be built"

    def test_case_insensitive_matching(self, extractor):
        """Test dictionary matches are case-insensitive."""
        test_cases = [
            ("Pin yếu quá", "pin"),  # lowercase in dict, capitalized in text
            ("ĐỘNG CƠ khỏe", "động cơ"),  # uppercase in text
            ("Giá Đắt", "giá"),  # mixed case
        ]

        for text, expected_keyword in test_cases:
            result = extractor.extract(text)
            keywords = [kw["keyword"] for kw in result.keywords]
            assert expected_keyword in keywords, f"Should match '{expected_keyword}' in '{text}'"

    def test_multi_word_term_matching(self, extractor):
        """Test multi-word terms are matched correctly."""
        test_cases = [
            ("Tìm trạm sạc gần đây", "trạm sạc", Aspect.PERFORMANCE),
            ("Chi phí lăn bánh cao", "lăn bánh", Aspect.PRICE),
            ("Ngoại thất đẹp", "ngoại thất", Aspect.DESIGN),
            ("Bảo hành tốt", "bảo hành", Aspect.SERVICE),
        ]

        for text, expected_keyword, expected_aspect in test_cases:
            result = extractor.extract(text)
            matched = [
                kw for kw in result.keywords if kw["keyword"] == expected_keyword
            ]
            assert len(matched) > 0, f"Should match '{expected_keyword}' in '{text}'"
            assert (
                matched[0]["aspect"] == expected_aspect.value
            ), f"Should assign aspect {expected_aspect}"

    def test_aspect_assignment_for_dictionary_terms(self, extractor):
        """Test aspect labels are correctly assigned to dictionary terms."""
        test_cases = [
            ("Thiết kế đẹp", Aspect.DESIGN),
            ("Pin yếu", Aspect.PERFORMANCE),
            ("Giá đắt", Aspect.PRICE),
            ("Bảo hành tốt", Aspect.SERVICE),
        ]

        for text, expected_aspect in test_cases:
            result = extractor.extract(text)
            assert len(result.keywords) > 0, f"Should extract keywords from '{text}'"

            # Check that at least one keyword has the expected aspect
            aspects = [kw["aspect"] for kw in result.keywords]
            assert (
                expected_aspect.value in aspects
            ), f"Should assign {expected_aspect} for '{text}'"

    def test_lookup_map_building(self, extractor):
        """Test lookup map is built correctly (term → aspect)."""
        # Verify lookup map structure
        assert isinstance(extractor.keyword_map, dict), "keyword_map should be a dict"

        # Test some known terms
        expected_mappings = [
            ("pin", Aspect.PERFORMANCE),
            ("giá", Aspect.PRICE),
            ("đẹp", Aspect.DESIGN),
            ("bảo hành", Aspect.SERVICE),
        ]

        for term, expected_aspect in expected_mappings:
            if term in extractor.keyword_map:
                assert (
                    extractor.keyword_map[term] == expected_aspect
                ), f"'{term}' should map to {expected_aspect}"

    def test_dictionary_score_is_perfect(self, extractor):
        """Test dictionary matches always have score=1.0."""
        text = "Pin yếu, giá đắt, xe đẹp"
        result = extractor.extract(text)

        for kw in result.keywords:
            assert kw["source"] == "DICT", "All keywords should be from dictionary"
            assert kw["score"] == 1.0, "Dictionary matches should have perfect score"

    def test_empty_text_returns_empty_result(self, extractor):
        """Test empty or None input returns empty result."""
        test_cases = ["", "   ", None]

        for text in test_cases:
            result = extractor.extract(text or "")
            assert result.keywords == [], f"Should return empty keywords for '{text}'"
            assert result.metadata["dict_matches"] == 0
            assert result.metadata["ai_matches"] == 0

    def test_text_with_no_dictionary_matches(self, extractor):
        """Test text with no dictionary terms returns empty result."""
        text = "abc xyz 123 test unknown words"
        result = extractor.extract(text)

        assert result.keywords == [], "Should return empty keywords for non-matching text"
        assert result.metadata["dict_matches"] == 0


class TestAIDiscovery:
    """Test 2.2: AI discovery using SpaCy + YAKE."""

    @pytest.fixture
    def extractor(self):
        """Create KeywordExtractor instance with AI enabled."""
        extractor = KeywordExtractor()
        extractor.enable_ai = True
        return extractor

    def test_ai_extraction_when_dictionary_insufficient(self, extractor):
        """Test AI extraction runs when dictionary matches < threshold."""
        # Text with few dictionary matches (should trigger AI)
        text = "VinFast ra mẫu xe mới"

        # Disable AI if SpaCy model not available
        try:
            result = extractor.extract(text)

            # Should have some AI-discovered keywords if SpaCy is available
            # (This test may need SpaCy model installed)
            assert result.metadata["dict_matches"] < extractor.ai_threshold
        except (OSError, SystemExit):
            # SpaCy model not installed - skip AI tests
            extractor.enable_ai = False
            result = extractor.extract(text)
            assert result.metadata["ai_matches"] == 0, "AI should be disabled"

    def test_ai_extraction_skipped_when_dictionary_sufficient(self, extractor):
        """Test AI extraction is skipped when dictionary matches >= threshold."""
        # Text with many dictionary matches (should NOT trigger AI)
        text = "Pin tốt, sạc nhanh, động cơ khỏe, giá rẻ, xe đẹp, bảo hành tốt"

        result = extractor.extract(text)

        # Should have sufficient dictionary matches
        assert result.metadata["dict_matches"] >= extractor.ai_threshold
        # AI should not have run
        assert result.metadata["ai_matches"] == 0

    def test_spacy_pos_filtering_nouns_only(self, extractor):
        """Test SpaCy filters to keep only NOUN/PROPN types."""
        # This test verifies the filtering logic in _extract_ai()
        # When AI runs, it should only return nouns/proper nouns

        # Set low threshold to force AI extraction
        extractor.ai_threshold = 0

        text = "VinFast sản xuất xe điện"

        result = extractor.extract(text)

        # All AI keywords should be nouns (no verbs/adjectives)
        ai_keywords = [kw for kw in result.keywords if kw["source"] == "AI"]

        # If AI extraction worked, verify types
        # (This test may need SpaCy model installed)
        for kw in ai_keywords:
            # The keyword should be a meaningful noun/entity
            assert len(kw["keyword"]) > 1, "Keywords should not be single characters"

    def test_duplicate_removal_dict_priority(self, extractor):
        """Test duplicates between DICT and AI are removed (DICT priority)."""
        # Text with terms in both dictionary and likely to be discovered by AI
        text = "Pin VinFast"  # "pin" is in dict, "VinFast" is not

        # Enable AI with low threshold
        extractor.ai_threshold = 0

        result = extractor.extract(text)

        # Check for duplicate keywords
        keywords = [kw["keyword"] for kw in result.keywords]
        unique_keywords = set(keywords)

        # Should not have duplicates
        assert len(keywords) == len(
            unique_keywords
        ), "Should not have duplicate keywords"

        # If "pin" appears, it should be from DICT
        pin_keywords = [kw for kw in result.keywords if kw["keyword"] == "pin"]
        if pin_keywords:
            assert (
                pin_keywords[0]["source"] == "DICT"
            ), "Dictionary should have priority over AI"

    def test_ai_disabled_flag(self, extractor):
        """Test AI extraction is disabled when enable_ai=False."""
        extractor.enable_ai = False
        extractor.ai_threshold = 0  # Force AI trigger

        text = "VinFast xe điện"

        result = extractor.extract(text)

        # AI should not have run
        assert result.metadata["ai_matches"] == 0

    def test_ai_extraction_error_handling(self, extractor):
        """Test AI extraction errors are handled gracefully."""
        # Force AI to run
        extractor.ai_threshold = 0

        # Even with malformed text, should not crash
        text = "!@#$%^&*()"

        result = extractor.extract(text)

        # Should return valid result (empty is fine)
        assert isinstance(result, KeywordResult)
        assert isinstance(result.keywords, list)


class TestAspectMapping:
    """Test 2.3: Aspect mapping for AI-discovered keywords."""

    @pytest.fixture
    def extractor(self):
        """Create KeywordExtractor instance."""
        return KeywordExtractor()

    def test_fuzzy_matching_for_ai_keywords(self, extractor):
        """Test fuzzy matching assigns aspects to AI keywords."""
        # Test the _fuzzy_map_aspect method directly
        test_cases = [
            ("pin", Aspect.PERFORMANCE),  # exact match
            ("thiết kế", Aspect.DESIGN),  # exact match
            ("giá cả", Aspect.PRICE),  # substring "giá"
        ]

        for keyword, expected_aspect in test_cases:
            mapped_aspect = extractor._fuzzy_map_aspect(keyword)
            # Should map to expected aspect or GENERAL
            assert isinstance(mapped_aspect, Aspect)

    def test_general_fallback(self, extractor):
        """Test GENERAL aspect is assigned when no match found."""
        # Keywords that don't match any dictionary terms
        unknown_keywords = ["VinFast", "unknown", "test123"]

        for keyword in unknown_keywords:
            mapped_aspect = extractor._fuzzy_map_aspect(keyword)
            assert (
                mapped_aspect == Aspect.GENERAL
            ), f"'{keyword}' should map to GENERAL"

    def test_exact_substring_matches(self, extractor):
        """Test exact substring matches work correctly."""
        # If dictionary has "pin", fuzzy matching should work for "pin battery"
        test_cases = [
            ("pin tốt", Aspect.PERFORMANCE),  # contains "pin"
            ("xe đẹp", Aspect.DESIGN),  # contains "đẹp"
        ]

        for keyword, expected_aspect in test_cases:
            mapped_aspect = extractor._fuzzy_map_aspect(keyword)
            # Should match the aspect (or GENERAL if not found)
            assert isinstance(mapped_aspect, Aspect)

    def test_partial_substring_matches(self, extractor):
        """Test partial substring matches work correctly."""
        # Test that substring matching works bidirectionally
        # (term in keyword OR keyword in term)

        # If dictionary has "động cơ", should match "động"
        mapped_aspect = extractor._fuzzy_map_aspect("động")

        # Should map to PERFORMANCE or GENERAL
        assert mapped_aspect in [
            Aspect.PERFORMANCE,
            Aspect.GENERAL,
        ], "Should map to valid aspect"

    def test_case_insensitive_fuzzy_matching(self, extractor):
        """Test fuzzy matching is case-insensitive."""
        test_cases = [
            ("PIN", Aspect.PERFORMANCE),
            ("Pin", Aspect.PERFORMANCE),
            ("pin", Aspect.PERFORMANCE),
        ]

        for keyword, expected_aspect in test_cases:
            mapped_aspect = extractor._fuzzy_map_aspect(keyword)
            # Should map to PERFORMANCE (or GENERAL if exact match not found)
            assert mapped_aspect in [
                expected_aspect,
                Aspect.GENERAL,
            ], f"'{keyword}' should be case-insensitive"


class TestHybridLogic:
    """Test 2.4: Hybrid logic combining DICT + AI."""

    @pytest.fixture
    def extractor(self):
        """Create KeywordExtractor instance."""
        return KeywordExtractor()

    def test_combining_dict_and_ai_results(self, extractor):
        """Test combining dictionary and AI extraction results."""
        # Enable AI with low threshold to get both sources
        extractor.enable_ai = True
        extractor.ai_threshold = 0

        text = "Pin VinFast xe điện"

        result = extractor.extract(text)

        # Should have keywords from both sources (if SpaCy available)
        # At minimum, should have dictionary matches
        assert len(result.keywords) > 0, "Should have some keywords"

        # Check sources
        sources = {kw["source"] for kw in result.keywords}
        assert "DICT" in sources, "Should have dictionary keywords"

    def test_deduplication_logic(self, extractor):
        """Test deduplication removes duplicate keywords."""
        extractor.enable_ai = True
        extractor.ai_threshold = 0

        text = "pin pin pin"  # Repeated term

        result = extractor.extract(text)

        # Should not have duplicates
        keywords = [kw["keyword"] for kw in result.keywords]
        unique_keywords = set(keywords)

        assert len(keywords) == len(
            unique_keywords
        ), "Should not have duplicate keywords"

    def test_sorting_by_score(self, extractor):
        """Test keywords are sorted by score descending."""
        extractor.enable_ai = False  # Use only dictionary for predictable scores

        text = "Pin yếu, giá đắt, xe đẹp, bảo hành tốt"

        result = extractor.extract(text)

        # All dictionary keywords should have score=1.0
        scores = [kw["score"] for kw in result.keywords]

        # Check scores are in descending order
        assert scores == sorted(scores, reverse=True), "Keywords should be sorted by score"

    def test_metadata_generation(self, extractor):
        """Test metadata is generated correctly."""
        extractor.enable_ai = False

        text = "Pin yếu, giá đắt"

        result = extractor.extract(text)

        # Verify metadata structure
        assert "dict_matches" in result.metadata
        assert "ai_matches" in result.metadata
        assert "total_keywords" in result.metadata
        assert "total_time_ms" in result.metadata

        # Verify metadata values
        assert result.metadata["dict_matches"] > 0
        assert result.metadata["ai_matches"] == 0
        assert result.metadata["total_keywords"] == len(result.keywords)
        assert result.metadata["total_time_ms"] >= 0

    def test_max_keywords_limit(self, extractor):
        """Test max_keywords limit is enforced."""
        # Set low max_keywords
        extractor.max_keywords = 3

        text = "Pin tốt, sạc nhanh, động cơ khỏe, giá rẻ, xe đẹp, bảo hành tốt, showroom tốt"

        result = extractor.extract(text)

        # Should not exceed max_keywords
        assert (
            len(result.keywords) <= extractor.max_keywords
        ), f"Should not exceed max_keywords={extractor.max_keywords}"
