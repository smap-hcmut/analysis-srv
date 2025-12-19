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

    def test_merge_cleanup_trailing_punctuation(self, preprocessor):
        """Test that trailing punctuation is removed before joining."""
        caption = "Great product."
        transcription = "Video content..."
        comments = [{"text": "Comment!", "likes": 10}]

        result = preprocessor.merge_content(
            caption=caption, transcription=transcription, comments=comments
        )

        # Should have clean separation with single periods
        assert result == "Video content. Great product. Comment"
        assert ".." not in result

    def test_merge_cleanup_duplicate_periods(self, preprocessor):
        """Test that duplicate periods are removed."""
        # Create input that would naturally create duplicate periods
        caption = "Test.."
        transcription = "Content..."

        result = preprocessor.merge_content(caption=caption, transcription=transcription)

        # Should not have duplicate periods
        assert ".." not in result
        assert "..." not in result

    def test_merge_cleanup_mixed_punctuation(self, preprocessor):
        """Test cleanup with mixed trailing punctuation."""
        caption = "Caption!!!"
        transcription = "Video???"
        comments = [{"text": "Comment;;;", "likes": 5}]

        result = preprocessor.merge_content(
            caption=caption, transcription=transcription, comments=comments
        )

        # Trailing punctuation should be stripped, clean periods added
        assert result == "Video. Caption. Comment"


class TestTextPreprocessorTeencode:
    """Tests for teencode normalization functionality."""

    @pytest.fixture
    def preprocessor(self):
        return TextPreprocessor()

    def test_normalize_teencode_ko(self, preprocessor):
        """Test 'ko' → 'không' replacement."""
        text = "Tôi ko biết"
        assert preprocessor._normalize_teencode(text) == "Tôi không biết"

    def test_normalize_teencode_vkl(self, preprocessor):
        """Test 'vkl' → 'rất' replacement."""
        text = "Đẹp vkl"
        assert preprocessor._normalize_teencode(text) == "Đẹp rất"

    def test_normalize_teencode_ae(self, preprocessor):
        """Test 'ae' → 'anh em' replacement."""
        text = "ae ơi"
        assert preprocessor._normalize_teencode(text) == "anh em ơi"

    def test_normalize_teencode_multiple(self, preprocessor):
        """Test multiple teencode replacements in one text."""
        text = "ko biết vkl ae ơi"
        assert preprocessor._normalize_teencode(text) == "không biết rất anh em ơi"

    def test_normalize_teencode_word_boundary(self, preprocessor):
        """Test word-boundary matching (avoid partial replacements)."""
        # 'ko' should not match in 'koko' or 'korea'
        text = "ko koko korea"
        result = preprocessor._normalize_teencode(text)
        # Only the first 'ko' should be replaced
        assert "không" in result
        assert "koko" in result.lower()  # koko should remain unchanged
        assert "korea" in result.lower()  # korea should remain unchanged

    def test_normalize_teencode_case_insensitive(self, preprocessor):
        """Test case-insensitive matching."""
        text = "Ko KO kO ko"
        result = preprocessor._normalize_teencode(text)
        # All variants should be replaced
        assert result.count("không") == 4

    def test_normalize_teencode_integrated(self, preprocessor):
        """Test teencode normalization in full normalize() pipeline."""
        text = "Sản phẩm ko tốt vkl ae ơi"
        normalized = preprocessor.normalize(text)
        # Should have teencode replaced and be lowercased
        assert "không" in normalized
        assert "rất" in normalized
        assert "anh em" in normalized


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

    def test_normalize_special_fonts(self, preprocessor):
        """Test NFKC conversion of mathematical alphanumeric symbols (special fonts)."""
        # Mathematical Alphanumeric Symbols (common in TikTok/Facebook stylized text)
        text = "𝐻𝑜𝑡 𝑇𝑟𝑒𝑛𝑑"  # Special font
        normalized = preprocessor.normalize(text)
        # Should convert to regular ASCII letters
        assert "hot" in normalized
        assert "trend" in normalized
        assert normalized == "hot trend"

    def test_normalize_special_fonts_mixed(self, preprocessor):
        """Test NFKC with special fonts mixed with Vietnamese."""
        text = "𝑋𝑒 𝑉𝑖𝑛𝐹𝑎𝑠𝑡 rất đẹp"
        normalized = preprocessor.normalize(text)
        # Special fonts converted, Vietnamese preserved
        assert "xe" in normalized
        assert "vinfast" in normalized
        assert "đẹp" in normalized

    def test_normalize_combined(self, preprocessor):
        """Test all normalization steps together."""
        text = "  HOT DEAL!!! 🔥 #Sale tại https://shop.com  "
        # Expected: lowercase, no emoji, no url, no #, clean spaces
        assert preprocessor.normalize(text) == "hot deal!!! sale tại"


class TestTextPreprocessorSpamDetection:
    """Tests for spam detection functionality."""

    @pytest.fixture
    def preprocessor(self):
        return TextPreprocessor()

    def test_detect_phone_number(self, preprocessor):
        """Test Vietnamese phone number detection."""
        # Test various phone number formats (10 digits total)
        assert preprocessor._detect_spam_signals("Liên hệ 0912345678")["has_phone"] == True
        assert preprocessor._detect_spam_signals("Call 0398765432")["has_phone"] == True
        assert preprocessor._detect_spam_signals("Zalo 0812345678")["has_phone"] == True
        assert preprocessor._detect_spam_signals("Số: 0712345678")["has_phone"] == True
        assert preprocessor._detect_spam_signals("No phone here")["has_phone"] == False

    def test_detect_spam_keywords(self, preprocessor):
        """Test spam keyword detection."""
        assert preprocessor._detect_spam_signals("Vay vốn nhanh")["has_spam_keyword"] == True
        assert preprocessor._detect_spam_signals("Lãi suất thấp")["has_spam_keyword"] == True
        assert preprocessor._detect_spam_signals("Giải ngân trong ngày")["has_spam_keyword"] == True
        assert preprocessor._detect_spam_signals("Bán sim đẹp")["has_spam_keyword"] == True
        assert preprocessor._detect_spam_signals("Tuyển dụng gấp")["has_spam_keyword"] == True
        assert preprocessor._detect_spam_signals("Normal content")["has_spam_keyword"] == False

    def test_detect_spam_keywords_case_insensitive(self, preprocessor):
        """Test spam keyword detection is case-insensitive."""
        assert preprocessor._detect_spam_signals("VAY VỐN nhanh")["has_spam_keyword"] == True
        assert preprocessor._detect_spam_signals("LÃI SUẤT thấp")["has_spam_keyword"] == True

    def test_detect_both_phone_and_spam(self, preprocessor):
        """Test detection of both phone and spam keywords."""
        result = preprocessor._detect_spam_signals("Vay vốn 0912345678")
        assert result["has_phone"] == True
        assert result["has_spam_keyword"] == True

    def test_calculate_stats_with_spam_signals(self, preprocessor):
        """Test that calculate_stats includes spam signals."""
        original = "Vay vốn lãi suất thấp. Liên hệ 0912345678"
        clean = "vay vốn lãi suất thấp. liên hệ 0912345678"

        stats = preprocessor.calculate_stats(original, clean, has_transcription=False)

        assert "has_phone" in stats
        assert "has_spam_keyword" in stats
        assert stats["has_phone"] == True
        assert stats["has_spam_keyword"] == True

    def test_calculate_stats_no_spam(self, preprocessor):
        """Test that calculate_stats detects no spam in clean content."""
        original = "Xe chạy rất êm và tiết kiệm nhiên liệu"
        clean = "xe chạy rất êm và tiết kiệm nhiên liệu"

        stats = preprocessor.calculate_stats(original, clean, has_transcription=False)

        assert stats["has_phone"] == False
        assert stats["has_spam_keyword"] == False


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
