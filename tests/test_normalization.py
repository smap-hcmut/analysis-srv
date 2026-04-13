"""Unit tests for internal/normalization/usecase/helpers.py.

Covers:
  - canonicalize_language_label
  - Language detection for English, Vietnamese, mixed, unsupported
  - Edge cases: empty text, emoji-only, URL-only, explicit language
  - Text quality flags
"""

from __future__ import annotations

import pytest

from internal.normalization.usecase.helpers import (
    TextNormResult,
    canonicalize_language_label,
    normalize_social_text,
)


# ---------------------------------------------------------------------------
# canonicalize_language_label
# ---------------------------------------------------------------------------


class TestCanonicalizeLanguageLabel:
    def test_none_returns_unknown(self):
        assert canonicalize_language_label(None) == "unknown"

    def test_fasttext_label_prefix_stripped(self):
        assert canonicalize_language_label("__label__en") == "en"

    def test_underscore_replaced(self):
        assert canonicalize_language_label("zh_tw") == "zh"

    def test_jp_mapped_to_ja(self):
        assert canonicalize_language_label("jp") == "ja"

    def test_in_mapped_to_id(self):
        assert canonicalize_language_label("in") == "id"

    def test_lowercase_normalised(self):
        assert canonicalize_language_label("EN") == "en"

    def test_empty_returns_unknown(self):
        assert canonicalize_language_label("") == "unknown"

    def test_whitespace_stripped(self):
        assert canonicalize_language_label("  vi  ") == "vi"


# ---------------------------------------------------------------------------
# Language detection — English text
# ---------------------------------------------------------------------------


class TestEnglishDetection:
    """Previously broken — all these cases returned 'unsupported'."""

    def test_basic_english(self):
        r = normalize_social_text("the product is good and fast", None, None)
        assert r.language == "en"
        assert r.language_supported is True

    def test_english_with_capitalised_words(self):
        r = normalize_social_text(
            "Great product highly recommend it to everyone", None, None
        )
        assert r.language == "en"
        assert r.language_supported is True

    def test_english_short_sentence(self):
        r = normalize_social_text("I agree great product!", None, None)
        assert r.language == "en"
        assert r.language_supported is True

    def test_english_question(self):
        r = normalize_social_text("What do you think about this?", None, None)
        assert r.language == "en"
        assert r.language_supported is True

    def test_english_exclamation(self):
        r = normalize_social_text("Absolutely love it! Best purchase ever.", None, None)
        assert r.language == "en"
        assert r.language_supported is True

    def test_english_review_style(self):
        r = normalize_social_text("Really nice quality, would buy again.", None, None)
        assert r.language == "en"
        assert r.language_supported is True

    def test_english_ascii_fallback(self):
        # Longer purely ASCII text with no common stopwords — hits ascii fallback
        r = normalize_social_text(
            "Impressive battery performance throughout entire working day.",
            None,
            None,
        )
        assert r.language in {"en", "mixed"}
        assert r.language_supported is True


# ---------------------------------------------------------------------------
# Language detection — Vietnamese text
# ---------------------------------------------------------------------------


class TestVietnameseDetection:
    def test_vi_with_diacritics(self):
        r = normalize_social_text("Sản phẩm này rất tốt", None, None)
        assert r.language == "vi"
        assert r.language_supported is True

    def test_vi_stopword_only(self):
        r = normalize_social_text("không nhanh lắm nhưng ổn", None, None)
        assert r.language == "vi"
        assert r.language_supported is True

    def test_vi_slang_normalised(self):
        r = normalize_social_text("sp ko dc giao nhanh", None, None)
        # After slang expansion: "sản phẩm không được giao nhanh".
        # ASCII words "giao"/"nhanh" may trigger mixed_bridge → "mixed" is also valid.
        assert r.language in {"vi", "mixed"}
        assert r.language_supported is True


# ---------------------------------------------------------------------------
# Language detection — Mixed text
# ---------------------------------------------------------------------------


class TestMixedDetection:
    def test_mixed_vi_en(self):
        r = normalize_social_text("Product chất lượng tốt great", None, None)
        assert r.language == "mixed"
        assert r.language_supported is True


# ---------------------------------------------------------------------------
# Language detection — Unsupported / other languages
# ---------------------------------------------------------------------------


class TestUnsupportedDetection:
    def test_indonesian_is_unsupported(self):
        r = normalize_social_text("banget bagus sangat produk ini", None, None)
        assert r.language_supported is False

    def test_empty_text_unsupported(self):
        r = normalize_social_text("", None, None)
        assert r.language_supported is False

    def test_url_only_unsupported(self):
        r = normalize_social_text("https://example.com/product", None, None)
        assert r.language_supported is False


# ---------------------------------------------------------------------------
# Explicit language override
# ---------------------------------------------------------------------------


class TestExplicitLanguage:
    def test_explicit_language_source_is_explicit(self):
        """Provider source must be 'explicit' when explicit_language is given."""
        r = normalize_social_text("sản phẩm này rất tốt", None, "vi")
        assert r.language_source == "explicit"

    def test_explicit_vi_on_vi_text_accepted(self):
        """Explicit vi + Vietnamese text → gate accepts it as vi or mixed."""
        r = normalize_social_text("sản phẩm này rất tốt", None, "vi")
        assert r.language in {"vi", "mixed"}
        assert r.language_supported is True

    def test_explicit_en_on_en_text_accepted(self):
        """Explicit en + English text → gate accepts it as en or mixed."""
        r = normalize_social_text("the product is really good", None, "en")
        assert r.language in {"en", "mixed"}
        assert r.language_supported is True

    def test_explicit_fasttext_label_normalised(self):
        """__label__vi prefix is stripped before use; Vietnamese text is accepted."""
        r = normalize_social_text("sản phẩm rất tốt", None, "__label__vi")
        assert r.language_source == "explicit"
        assert r.language in {"vi", "mixed"}
        assert r.language_supported is True


# ---------------------------------------------------------------------------
# Text extraction utilities
# ---------------------------------------------------------------------------


class TestTextExtraction:
    def test_url_extracted(self):
        r = normalize_social_text("check https://example.com now", None, None)
        assert "https://example.com" in r.urls

    def test_hashtag_extracted(self):
        r = normalize_social_text("love this #NewProduct review", None, None)
        assert "newproduct" in r.hashtags

    def test_emoji_extracted(self):
        r = normalize_social_text("Great product 😍🔥", None, None)
        assert len(r.emojis) >= 1

    def test_explicit_hashtags_merged(self):
        r = normalize_social_text("nice phone", ["#VinFast"], None)
        assert "vinfast" in r.hashtags


# ---------------------------------------------------------------------------
# Text quality flags
# ---------------------------------------------------------------------------


class TestTextQualityFlags:
    def test_normal_text_no_flags(self):
        r = normalize_social_text(
            "This phone is really great, highly recommend it.", None, None
        )
        assert r.text_quality_label == "normal"

    def test_unsupported_language_flag(self):
        r = normalize_social_text("αβγδεζ", None, None)
        assert "unsupported_language" in r.text_quality_flags

    def test_low_information_flag(self):
        r = normalize_social_text("ok", None, None)
        assert "low_information" in r.text_quality_flags


# ---------------------------------------------------------------------------
# Result fields completeness
# ---------------------------------------------------------------------------


class TestResultFields:
    def test_result_is_textnormresult(self):
        r = normalize_social_text("the product is good", None, None)
        assert isinstance(r, TextNormResult)

    def test_raw_text_preserved(self):
        r = normalize_social_text("  hello world  ", None, None)
        assert r.raw_text == "hello world"

    def test_language_confidence_positive_for_supported(self):
        r = normalize_social_text("the product is good", None, None)
        assert r.language_confidence > 0

    def test_semantic_route_hint_set(self):
        r = normalize_social_text("great product quality", None, None)
        assert r.semantic_route_hint in {
            "semantic_full",
            "semantic_lite",
            "semantic_skip",
        }
