"""Unit tests for TextPreprocessor module."""

import pytest  # type: ignore
from services.analytics.preprocessing.text_preprocessor import TextPreprocessor


class TestTextPreprocessorMerging:
    """Tests for content merging functionality."""

    @pytest.fixture
    def preprocessor(self):
        return TextPreprocessor()

    def test_merge_all_sources(self, preprocessor):
        """Test merging caption, transcription, and comments."""
        caption = "Caption text"
        transcription = "Video transcription"
        comments = [{"text": "Comment 1", "likes": 10}]

        result = preprocessor.merge_content(
            caption=caption, transcription=transcription, comments=comments
        )

        # Priority: Transcription > Caption > Comments
        assert result == "Video transcription. Caption text. Comment 1"

    def test_merge_transcription_only(self, preprocessor):
        """Test merging with only transcription."""
        result = preprocessor.merge_content(transcription="Transcription only")
        assert result == "Transcription only"

    def test_merge_caption_only(self, preprocessor):
        """Test merging with only caption."""
        result = preprocessor.merge_content(caption="Caption only")
        assert result == "Caption only"

    def test_merge_comments_sorting(self, preprocessor):
        """Test that comments are sorted by likes."""
        comments = [
            {"text": "Low likes", "likes": 1},
            {"text": "High likes", "likes": 100},
            {"text": "Medium likes", "likes": 50},
        ]

        result = preprocessor.merge_content(comments=comments, max_comments=3)
        expected = "High likes. Medium likes. Low likes"
        assert result == expected

    def test_merge_max_comments_limit(self, preprocessor):
        """Test that max_comments limit is respected."""
        comments = [{"text": f"Comment {i}", "likes": i} for i in range(10)]

        result = preprocessor.merge_content(comments=comments, max_comments=3)

        # Should only have top 3 (Comment 9, Comment 8, Comment 7)
        assert "Comment 9" in result
        assert "Comment 8" in result
        assert "Comment 7" in result
        assert "Comment 6" not in result
        assert result.count("Comment") == 3

    def test_merge_empty_inputs(self, preprocessor):
        """Test merging with empty or None inputs."""
        assert preprocessor.merge_content() == ""
        assert preprocessor.merge_content(caption="", transcription=None, comments=[]) == ""


class TestTextPreprocessorNormalization:
    """Tests for text normalization functionality."""

    @pytest.fixture
    def preprocessor(self):
        return TextPreprocessor()

    def test_normalize_urls(self, preprocessor):
        """Test URL removal."""
        text = "Check http://test.com and https://secure.com/path"
        assert preprocessor.normalize(text) == "check and"

    def test_normalize_emojis(self, preprocessor):
        """Test emoji removal."""
        text = "Great product! 😍🔥👍"
        assert preprocessor.normalize(text) == "great product!"

    def test_normalize_hashtags(self, preprocessor):
        """Test hashtag processing (remove #, keep word)."""
        text = "Review of #VinFast #VF3 car"
        assert preprocessor.normalize(text) == "review of vinfast vf3 car"

    def test_normalize_whitespace(self, preprocessor):
        """Test whitespace normalization."""
        text = "  Multiple    spaces   and\nnewlines  "
        assert preprocessor.normalize(text) == "multiple spaces and newlines"

    def test_normalize_lowercase(self, preprocessor):
        """Test lowercase conversion."""
        text = "UPPER Case Text"
        assert preprocessor.normalize(text) == "upper case text"

    def test_normalize_vietnamese(self, preprocessor):
        """Test Vietnamese Unicode normalization."""
        # Composed vs Decomposed forms
        composed = "Tiếng Việt"
        decomposed = "Tiếng Việt"  # Visually similar but different bytes

        norm_composed = preprocessor.normalize(composed)
        norm_decomposed = preprocessor.normalize(decomposed)

        assert norm_composed == norm_decomposed
        assert norm_composed == "tiếng việt"

    def test_normalize_combined(self, preprocessor):
        """Test all normalization steps together."""
        text = "  HOT DEAL!!! 🔥 #Sale tại https://shop.com  "
        # Expected: lowercase, no emoji, no url, no #, clean spaces
        assert preprocessor.normalize(text) == "hot deal!!! sale tại"


class TestTextPreprocessorStats:
    """Tests for statistics calculation."""

    @pytest.fixture
    def preprocessor(self):
        return TextPreprocessor()

    def test_calculate_stats_basic(self, preprocessor):
        """Test basic stats calculation."""
        original = "Hello World"
        clean = "hello world"

        stats = preprocessor.calculate_stats(original, clean, has_transcription=False)

        assert stats["total_length"] == 11
        assert stats["is_too_short"] == False
        assert stats["hashtag_ratio"] == 0.0
        assert stats["has_transcription"] == False

    def test_calculate_stats_short_text(self, preprocessor):
        """Test is_too_short flag."""
        original = "Hi"
        clean = "hi"

        stats = preprocessor.calculate_stats(original, clean, has_transcription=False)
        assert stats["is_too_short"] == True

    def test_calculate_stats_hashtags(self, preprocessor):
        """Test hashtag ratio."""
        original = "This is #spam #content #test"
        clean = "this is spam content test"

        stats = preprocessor.calculate_stats(original, clean, has_transcription=False)
        # 3 hashtags / 5 words = 0.6
        assert stats["hashtag_ratio"] == 0.6

    def test_calculate_stats_reduction(self, preprocessor):
        """Test reduction ratio."""
        original = "A" * 100
        clean = "A" * 50

        stats = preprocessor.calculate_stats(original, clean, has_transcription=False)
        assert stats["reduction_ratio"] == 0.5


class TestTextPreprocessorPipeline:
    """Tests for full pipeline."""

    @pytest.fixture
    def preprocessor(self):
        return TextPreprocessor()

    def test_preprocess_full_flow(self, preprocessor):
        """Test end-to-end preprocessing."""
        input_data = {
            "content": {"text": "Caption #test", "transcription": "Video content"},
            "comments": [{"text": "Comment 1", "likes": 5}],
        }

        result = preprocessor.preprocess(input_data)

        # Check clean text
        assert "video content" in result.clean_text
        assert "caption test" in result.clean_text
        assert "comment 1" in result.clean_text

        # Check stats
        assert result.stats["has_transcription"] == True
        assert result.stats["total_length"] > 0

        # Check breakdown
        assert result.source_breakdown["transcript_len"] > 0
        assert result.source_breakdown["caption_len"] > 0
        assert result.source_breakdown["comments_len"] > 0

    def test_preprocess_missing_fields(self, preprocessor):
        """Test pipeline with minimal input."""
        input_data = {}
        result = preprocessor.preprocess(input_data)

        assert result.clean_text == ""
        assert result.stats["total_length"] == 0
        assert result.stats["has_transcription"] == False
