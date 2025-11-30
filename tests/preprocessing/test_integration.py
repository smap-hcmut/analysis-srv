"""Integration tests for TextPreprocessor with real-world scenarios."""

import pytest  # type: ignore
from services.analytics.preprocessing.text_preprocessor import TextPreprocessor


class TestTextPreprocessorIntegration:
    """Integration tests using realistic data samples."""

    @pytest.fixture
    def preprocessor(self):
        return TextPreprocessor()

    def test_vietnamese_facebook_post(self, preprocessor):
        """Test with a typical Vietnamese Facebook post."""
        input_data = {
            "content": {
                "text": "VinFast VF3 chạy quá ngon! 🔥 Ae nên chốt đơn ngay. #VinFast #VF3 #Vietnam",
                "transcription": None,
            },
            "comments": [
                {"text": "Giá lăn bánh bao nhiêu shop?", "likes": 150},
                {"text": "Đẹp quá", "likes": 50},
                {"text": "Xe tàu thôi", "likes": 10},
            ],
        }

        result = preprocessor.preprocess(input_data)

        # Check normalization (teencode "ae" → "anh em")
        assert "vinfast vf3 chạy quá ngon" in result.clean_text
        assert "anh em nên chốt đơn ngay" in result.clean_text
        assert "giá lăn bánh bao nhiêu shop" in result.clean_text

        # Check hashtags removed but words kept
        assert "vinfast" in result.clean_text
        assert "#" not in result.clean_text

        # Check stats
        assert result.stats["has_transcription"] == False
        assert result.stats["hashtag_ratio"] > 0
        assert result.stats["is_too_short"] == False

    def test_tiktok_video_post(self, preprocessor):
        """Test with a TikTok video post (transcription heavy)."""
        input_data = {
            "content": {
                "text": "Review xe mới nè cả nhà #review #car",
                "transcription": "Xin chào mọi người hôm nay mình sẽ trải nghiệm chiếc xe điện mới nhất. Cảm giác lái rất đầm và chắc chắn.",
            },
            "comments": [
                {"text": "Clip hay quá", "likes": 1000},
                {"text": "Review chi tiết hơn đi", "likes": 500},
            ],
        }

        result = preprocessor.preprocess(input_data)

        # Transcription should be first
        assert result.clean_text.startswith("xin chào mọi người")

        # Check stats
        assert result.stats["has_transcription"] == True
        assert result.source_breakdown["transcript_len"] > result.source_breakdown["caption_len"]

    def test_spam_post_detection(self, preprocessor):
        """Test detection of spam/low quality posts."""
        # Case 1: Only hashtags
        spam_input = {
            "content": {"text": "#follow #like #share #f4f #l4l", "transcription": None},
            "comments": [],
        }

        result = preprocessor.preprocess(spam_input)

        # High hashtag ratio
        assert result.stats["hashtag_ratio"] == 1.0

        # Case 2: Too short
        short_input = {"content": {"text": "Hi"}, "comments": []}

        result_short = preprocessor.preprocess(short_input)
        assert result_short.stats["is_too_short"] == True

    def test_mixed_language_content(self, preprocessor):
        """Test with mixed English and Vietnamese content."""
        input_data = {
            "content": {
                "text": "Sản phẩm này rất good! Quality tuyệt vời. 5 stars ⭐️⭐️⭐️⭐️⭐️",
            },
            "comments": [],
        }

        result = preprocessor.preprocess(input_data)

        assert "sản phẩm này rất good" in result.clean_text
        assert "quality tuyệt vời" in result.clean_text
        assert "5 stars" in result.clean_text
        assert "⭐️" not in result.clean_text

    def test_complex_urls_and_mentions(self, preprocessor):
        """Test removal of complex URLs and mentions."""
        text = "Order at https://bit.ly/3xyz or www.shop.vn/promo?id=123 @username check inbox"
        input_data = {"content": {"text": text}, "comments": []}

        result = preprocessor.preprocess(input_data)

        # URLs removed
        assert "http" not in result.clean_text
        assert "www" not in result.clean_text
        # Mentions are not explicitly removed by regex (unless treated as special chars),
        # but let's check what remains.
        # Current regex doesn't remove @username, only URLs and emojis.
        # This test confirms current behavior.
        assert "@username" in result.clean_text
