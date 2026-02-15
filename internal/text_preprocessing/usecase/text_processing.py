import re
import unicodedata
from typing import Optional

from pkg.logger.logger import Logger
from internal.text_preprocessing.interface import ITextProcessing
from internal.text_preprocessing.type import *
from internal.text_preprocessing.constant import *


class TextProcessing(ITextProcessing):
    """Text processing use case."""

    def __init__(self, config: Config, logger: Optional[Logger] = None):
        """Initialize text processing use case.
        
        Args:
            config: Configuration for text processing
            logger: Logger instance (optional). If None, no logging will be performed.
        """
        self.config = config
        self.logger = logger
        self.min_text_length = config.min_text_length
        self.max_comments = config.max_comments

        self.url_pattern = re.compile(PATTERN_URL)
        self.emoji_pattern = re.compile(PATTERN_EMOJI, flags=re.UNICODE)
        self.hashtag_pattern = re.compile(PATTERN_HASHTAG)
        self.whitespace_pattern = re.compile(PATTERN_WHITESPACE)
        self.phone_pattern = re.compile(PATTERN_PHONE_VN)

        if self.logger:
            self.logger.info(
                "[TextProcessing] Initialized",
                extra={
                    "min_text_length": self.min_text_length,
                    "max_comments": self.max_comments,
                },
            )

    def _normalize_teencode(self, text: str) -> str:
        if not text:
            return ""

        try:
            result = text
            for slang, formal in TEENCODE_DICT.items():
                pattern = r"\b" + re.escape(slang) + r"\b"
                result = re.sub(pattern, formal, result, flags=re.IGNORECASE)
            return result
        except Exception as e:
            if self.logger:
                self.logger.error(
                    "[TextProcessing] Teencode normalization failed",
                    extra={"error": str(e), "text_len": len(text)},
                )
            raise

    def _detect_spam_signals(self, text: str) -> tuple[bool, bool]:
        if not text:
            return False, False

        try:
            has_phone = bool(self.phone_pattern.search(text))
            text_lower = text.lower()
            has_spam_keyword = any(keyword in text_lower for keyword in SPAM_KEYWORDS)

            if self.logger and (has_phone or has_spam_keyword):
                self.logger.warn(
                    "[TextProcessing] Spam signals detected",
                    extra={"has_phone": has_phone, "has_spam_keyword": has_spam_keyword},
                )

            return has_phone, has_spam_keyword
        except Exception as e:
            if self.logger:
                self.logger.error(
                    "[TextProcessing] Spam detection failed",
                    extra={"error": str(e)},
                )
            return False, False

    def merge_content(
        self,
        caption: str,
        comments: list[CommentInput],
        transcription: str,
        max_comments: Optional[int] = None,
    ) -> str:
        if max_comments is None:
            max_comments = self.max_comments

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

    def normalize(self, text: str) -> str:
        if not text:
            return ""

        text = unicodedata.normalize(UNICODE_NORMALIZATION_FORM, text)
        text = self._normalize_teencode(text)
        text = self.url_pattern.sub("", text)
        text = self.emoji_pattern.sub("", text)
        text = self.hashtag_pattern.sub(r"\1", text)
        text = self.whitespace_pattern.sub(" ", text)
        text = text.lower()
        text = text.strip()

        return text

    def calculate_stats(
        self, original_text: str, clean_text: str, has_transcription: bool
    ) -> Stats:
        total_length = len(clean_text)
        is_too_short = len(clean_text) < self.min_text_length

        hashtags = self.hashtag_pattern.findall(original_text)
        words = original_text.split()
        hashtag_ratio = len(hashtags) / len(words) if words else 0.0

        original_len = len(original_text)
        clean_len = len(clean_text)
        reduction_ratio = (
            (original_len - clean_len) / original_len if original_len > 0 else 0.0
        )

        has_phone, has_spam_keyword = self._detect_spam_signals(original_text)

        return Stats(
            total_length=total_length,
            is_too_short=is_too_short,
            hashtag_ratio=hashtag_ratio,
            reduction_ratio=reduction_ratio,
            has_transcription=has_transcription,
            has_phone=has_phone,
            has_spam_keyword=has_spam_keyword,
        )

    def process(self, input_data: Input) -> Output:
        """Process input data and return output.
        
        Args:
            input_data: Input structure with content and comments
            
        Returns:
            Output with clean text, stats, and source breakdown
            
        Raises:
            ValueError: If input_data is invalid
            Exception: If processing fails
        """
        if not isinstance(input_data, Input):
            error_msg = "input_data must be an instance of Input"
            if self.logger:
                self.logger.error(
                    "[TextProcessing] Invalid input type",
                    extra={"input_type": type(input_data).__name__},
                )
            raise ValueError(error_msg)

        try:

            caption = input_data.content.text
            transcription = input_data.content.transcription
            comments = input_data.comments

            if self.logger:
                self.logger.info(
                    "[TextProcessing] Processing started",
                    extra={
                        "caption_len": len(caption),
                        "transcription_len": len(transcription),
                        "comments_count": len(comments),
                    },
                )

            caption_len = len(caption)
            transcript_len = len(transcription)
            comments_len = sum(len(c.text) for c in comments[: self.max_comments])

            merged_text = self.merge_content(
                caption=caption, comments=comments, transcription=transcription
            )

            clean_text = self.normalize(merged_text)

            has_transcription = bool(transcription and transcription.strip())
            stats = self.calculate_stats(
                original_text=merged_text,
                clean_text=clean_text,
                has_transcription=has_transcription,
            )

            source_breakdown = SourceBreakdown(
                caption_len=caption_len,
                transcript_len=transcript_len,
                comments_len=comments_len,
            )

            if self.logger:
                self.logger.info(
                    "[TextProcessing] Processing completed",
                    extra={
                        "clean_text_len": stats.total_length,
                        "is_too_short": stats.is_too_short,
                        "has_spam": stats.has_phone or stats.has_spam_keyword,
                        "hashtag_ratio": stats.hashtag_ratio,
                        "reduction_ratio": stats.reduction_ratio,
                    },
                )

            return Output(
                clean_text=clean_text, stats=stats, source_breakdown=source_breakdown
            )

        except ValueError:
            raise
        except Exception as e:
            if self.logger:
                self.logger.error(
                    "[TextProcessing] Processing failed",
                    extra={"error": str(e), "error_type": type(e).__name__},
                )
            raise


__all__ = ["TextProcessing"]
