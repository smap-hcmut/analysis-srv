import re
import unicodedata
from typing import Optional, Pattern, Tuple, List

from pkg.logger.logger import Logger
from internal.text_preprocessing.type import CommentInput, Stats, SourceBreakdown
from internal.text_preprocessing.constant import *


def normalize_teencode(text: str, logger: Optional[Logger] = None) -> str:
    if not text:
        return ""

    try:
        result = text
        for slang, formal in TEENCODE_DICT.items():
            pattern = r"\b" + re.escape(slang) + r"\b"
            result = re.sub(pattern, formal, result, flags=re.IGNORECASE)
        return result
    except Exception as e:
        logger.error("internal.text_preprocessing.usecase.helpers.normalize_teencode: %s", e)
        raise


def detect_spam_signals(
    text: str, phone_pattern: Pattern, logger: Optional[Logger] = None
) -> Tuple[bool, bool]:
    if not text:
        return False, False

    try:
        has_phone = bool(phone_pattern.search(text))
        text_lower = text.lower()
        has_spam_keyword = any(keyword in text_lower for keyword in SPAM_KEYWORDS)

        logger.warn("internal.text_preprocessing.usecase.helpers.detect_spam_signals: Spam signals detected", extra={"has_phone": has_phone, "has_spam_keyword": has_spam_keyword})

        return has_phone, has_spam_keyword
    except Exception as e:
        logger.error("internal.text_preprocessing.usecase.helpers.detect_spam_signals: %s", e)
        return False, False


def merge_content(
    caption: str,
    comments: List[CommentInput],
    transcription: str,
    max_comments: int,
) -> str:
    parts = []

    if transcription and transcription.strip():
        cleaned = transcription.strip().rstrip(TRAILING_PUNCTUATION)
        if cleaned:
            parts.append(cleaned)

    if caption and caption.strip():
        cleaned = caption.strip().rstrip(TRAILING_PUNCTUATION)
        if cleaned:
            parts.append(cleaned)

    if comments:
        sorted_comments = sorted(comments, key=lambda c: c.likes, reverse=True)

        for comment in sorted_comments[:max_comments]:
            comment_text = comment.text.strip()
            if comment_text:
                cleaned = comment_text.rstrip(TRAILING_PUNCTUATION)
                if cleaned:
                    parts.append(cleaned)

    merged = ". ".join(parts) if parts else ""
    merged = re.sub(PATTERN_DUPLICATE_PERIODS, ".", merged)

    return merged


def normalize(
    text: str,
    url_pattern: Pattern,
    emoji_pattern: Pattern,
    hashtag_pattern: Pattern,
    whitespace_pattern: Pattern,
    logger: Optional[Logger] = None,
) -> str:
    if not text:
        return ""

    text = unicodedata.normalize(UNICODE_NORMALIZATION_FORM, text)
    text = normalize_teencode(text, logger)
    text = url_pattern.sub("", text)
    text = emoji_pattern.sub("", text)
    text = hashtag_pattern.sub(r"\1", text)
    text = whitespace_pattern.sub(" ", text)
    text = text.lower()
    text = text.strip()

    return text


def calculate_stats(
    original_text: str,
    clean_text: str,
    has_transcription: bool,
    min_text_length: int,
    hashtag_pattern: Pattern,
    phone_pattern: Pattern,
    logger: Optional[Logger] = None,
) -> Stats:
    total_length = len(clean_text)
    is_too_short = len(clean_text) < min_text_length

    hashtags = hashtag_pattern.findall(original_text)
    words = original_text.split()
    hashtag_ratio = len(hashtags) / len(words) if words else 0.0

    original_len = len(original_text)
    clean_len = len(clean_text)
    reduction_ratio = (
        (original_len - clean_len) / original_len if original_len > 0 else 0.0
    )

    has_phone, has_spam_keyword = detect_spam_signals(
        original_text, phone_pattern, logger
    )

    return Stats(
        total_length=total_length,
        is_too_short=is_too_short,
        hashtag_ratio=hashtag_ratio,
        reduction_ratio=reduction_ratio,
        has_transcription=has_transcription,
        has_phone=has_phone,
        has_spam_keyword=has_spam_keyword,
    )


def detect_spam(text: str, logger: Optional[Logger] = None) -> Tuple[bool, List[str]]:
    if not text or not isinstance(text, str):
        return False, []

    reasons = []

    if len(text.strip()) < MIN_TEXT_LENGTH:
        reasons.append("TEXT_TOO_SHORT")

    words = text.split()
    if len(words) > 0:
        distinct_words = len(set(words))
        diversity = distinct_words / len(words)
        if diversity < MIN_WORD_DIVERSITY:
            reasons.append(f"LOW_WORD_DIVERSITY_{diversity:.2f}")

    text_lower = text.lower()
    matched_ads = []
    for keyword in ADS_KEYWORDS:
        if keyword in text_lower:
            matched_ads.append(keyword)

    if matched_ads:
        reasons.append(f"ADS_KEYWORDS_{','.join(matched_ads)}")

    is_spam = len(reasons) > 0

    if is_spam:
        logger.debug("internal.text_preprocessing.usecase.helpers.detect_spam: Spam detected", extra={"reasons": reasons})

    return is_spam, reasons
