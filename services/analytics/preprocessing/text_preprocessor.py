"""Text preprocessing module for analytics pipeline.

This module provides the TextPreprocessor class which serves as Stage 1 of the
AI processing pipeline. It merges content from multiple sources, normalizes text,
and calculates noise statistics to help the orchestrator filter low-quality posts.

Role in Pipeline:
    Raw Atomic JSON → TextPreprocessor → Clean Text + Stats → Orchestrator → AI Models

Input Contract:
    {
        "content": {
            "text": "caption text...",  # Optional
            "transcription": "video transcript..."  # Optional, highest priority
        },
        "comments": [
            {"text": "comment text", "likes": 10},  # Sorted by likes
            ...
        ]
    }

Output Contract:
    {
        "clean_text": "normalized text for AI models",
        "stats": {
            "total_length": 150,
            "is_too_short": False,
            "hashtag_ratio": 0.05,
            "reduction_ratio": 0.15,
            "has_transcription": True
        },
        "source_breakdown": {
            "caption_len": 50,
            "transcript_len": 200,
            "comments_len": 30
        }
    }
"""

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional


from core.config import settings


@dataclass
class PreprocessingResult:
    """Result of text preprocessing.

    Attributes:
        clean_text: Normalized and cleaned text ready for AI models
        stats: Dictionary containing noise and quality statistics
        source_breakdown: Dictionary showing contribution from each source
    """

    clean_text: str
    stats: Dict[str, Any] = field(default_factory=dict)
    source_breakdown: Dict[str, int] = field(default_factory=dict)


class TextPreprocessor:
    """Text preprocessor for analytics pipeline.

    This class implements Stage 1 of the AI processing pipeline, providing:
    1. Content merging from multiple sources (transcription, caption, comments)
    2. Text normalization (Unicode, URLs, emojis, hashtags)
    3. Noise statistics calculation for filtering

    Example:
        >>> preprocessor = TextPreprocessor()
        >>> input_data = {
        ...     "content": {"text": "Check this out! #awesome"},
        ...     "comments": [{"text": "Great!", "likes": 5}]
        ... }
        >>> result = preprocessor.preprocess(input_data)
        >>> print(result.clean_text)
        'check this out awesome great'
    """

    def __init__(self):
        """Initialize preprocessor with compiled regex patterns."""
        # Configuration
        self.min_text_length = settings.preprocessor_min_text_length
        self.max_comments = settings.preprocessor_max_comments

        # URL pattern - matches http(s):// and www. URLs
        self.url_pattern = re.compile(
            r"(?:http[s]?://|www\.)(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+"
        )

        # Emoji pattern - Unicode ranges for common emojis
        self.emoji_pattern = re.compile(
            "["
            "\U0001f600-\U0001f64f"  # emoticons
            "\U0001f300-\U0001f5ff"  # symbols & pictographs
            "\U0001f680-\U0001f6ff"  # transport & map symbols
            "\U0001f1e0-\U0001f1ff"  # flags (iOS)
            "\U00002702-\U000027b0"
            "\U000024c2-\U0001f251"
            "]+",
            flags=re.UNICODE,
        )

        # Hashtag pattern - matches #word
        self.hashtag_pattern = re.compile(r"#(\w+)")

        # Whitespace normalization pattern
        self.whitespace_pattern = re.compile(r"\s+")

    def merge_content(
        self,
        caption: Optional[str] = None,
        comments: Optional[List[Dict[str, Any]]] = None,
        transcription: Optional[str] = None,
        max_comments: Optional[int] = None,
    ) -> str:
        """Merge content from multiple sources with priority ordering.

        Priority order:
        1. Transcription (highest - for video/audio content)
        2. Caption (medium - main post text)
        3. Top N comments sorted by likes (lowest - user engagement)

        Args:
            caption: Post caption/text
            comments: List of comment dicts with 'text' and 'likes' keys
            transcription: Video/audio transcription
            max_comments: Maximum number of comments to include (default: configured value)

        Returns:
            Merged text string with period separators

        Example:
            >>> preprocessor = TextPreprocessor()
            >>> merged = preprocessor.merge_content(
            ...     caption="Great product",
            ...     comments=[
            ...         {"text": "Where to buy?", "likes": 10},
            ...         {"text": "Awesome!", "likes": 5}
            ...     ]
            ... )
            >>> print(merged)
            'Great product. Where to buy? Awesome!'
        """
        # Use configured max_comments if not provided
        if max_comments is None:
            max_comments = self.max_comments

        parts = []

        # Priority 1: Transcription (if available)
        if transcription and transcription.strip():
            parts.append(transcription.strip())

        # Priority 2: Caption
        if caption and caption.strip():
            parts.append(caption.strip())

        # Priority 3: Top comments sorted by likes
        if comments:
            # Sort by likes (descending) and take top N
            sorted_comments = sorted(comments, key=lambda c: c.get("likes", 0), reverse=True)

            for comment in sorted_comments[:max_comments]:
                comment_text = comment.get("text", "").strip()
                if comment_text:
                    parts.append(comment_text)

        # Join with period separator
        return ". ".join(parts) if parts else ""

    def normalize(self, text: str) -> str:
        """Normalize text for AI model consumption.

        Normalization steps:
        1. Unicode NFC normalization (handles Vietnamese characters)
        2. Remove URLs
        3. Remove emojis
        4. Convert hashtags to plain text (remove # but keep word)
        5. Normalize whitespace (multiple spaces → single space)
        6. Convert to lowercase
        7. Strip leading/trailing whitespace

        Args:
            text: Raw text to normalize

        Returns:
            Cleaned and normalized text

        Example:
            >>> preprocessor = TextPreprocessor()
            >>> text = "Check out https://example.com #awesome 😀 Multiple   spaces"
            >>> normalized = preprocessor.normalize(text)
            >>> print(normalized)
            'check out awesome multiple spaces'
        """
        if not text:
            return ""

        # Step 1: Unicode NFC normalization (important for Vietnamese)
        text = unicodedata.normalize("NFC", text)

        # Step 2: Remove URLs
        text = self.url_pattern.sub("", text)

        # Step 3: Remove emojis
        text = self.emoji_pattern.sub("", text)

        # Step 4: Convert hashtags to plain text (keep the word, remove #)
        text = self.hashtag_pattern.sub(r"\1", text)

        # Step 5: Normalize whitespace
        text = self.whitespace_pattern.sub(" ", text)

        # Step 6: Convert to lowercase
        text = text.lower()

        # Step 7: Strip leading/trailing whitespace
        text = text.strip()

        return text

    def calculate_stats(
        self, original_text: str, clean_text: str, has_transcription: bool
    ) -> Dict[str, Any]:
        """Calculate noise and quality statistics.

        Statistics calculated:
        - total_length: Length of cleaned text
        - is_too_short: True if text < min_text_length
        - hashtag_ratio: Ratio of hashtags to total words in original
        - reduction_ratio: How much text was removed during cleaning
        - has_transcription: Whether transcription was available

        Args:
            original_text: Raw merged text before cleaning
            clean_text: Normalized text after cleaning
            has_transcription: Whether input had transcription

        Returns:
            Dictionary of statistics

        Example:
            >>> preprocessor = TextPreprocessor()
            >>> stats = preprocessor.calculate_stats(
            ...     original_text="Check #this #out http://example.com",
            ...     clean_text="check this out",
            ...     has_transcription=False
            ... )
            >>> stats['hashtag_ratio']
            0.5
        """
        stats = {}

        # Total length of cleaned text
        stats["total_length"] = len(clean_text)

        # Is text too short?
        stats["is_too_short"] = len(clean_text) < self.min_text_length

        # Calculate hashtag ratio
        hashtags = self.hashtag_pattern.findall(original_text)
        words = original_text.split()
        stats["hashtag_ratio"] = len(hashtags) / len(words) if words else 0.0

        # Calculate reduction ratio (how much was removed)
        original_len = len(original_text)
        clean_len = len(clean_text)
        stats["reduction_ratio"] = (
            (original_len - clean_len) / original_len if original_len > 0 else 0.0
        )

        # Has transcription flag
        stats["has_transcription"] = has_transcription

        return stats

    def preprocess(self, input_data: Dict[str, Any]) -> PreprocessingResult:
        """Main preprocessing pipeline entry point.

        This method orchestrates the full preprocessing workflow:
        1. Extract fields from input dict
        2. Track source lengths for breakdown
        3. Merge content from all sources
        4. Normalize the merged text
        5. Calculate statistics
        6. Build source breakdown
        7. Return PreprocessingResult

        Args:
            input_data: Input dictionary matching the contract:
                {
                    "content": {
                        "text": str,  # caption
                        "transcription": str  # optional
                    },
                    "comments": [{"text": str, "likes": int}, ...]
                }

        Returns:
            PreprocessingResult with clean_text, stats, and source_breakdown

        Example:
            >>> preprocessor = TextPreprocessor()
            >>> input_data = {
            ...     "content": {
            ...         "text": "Amazing product! #musthave",
            ...         "transcription": "Today I'm reviewing this product..."
            ...     },
            ...     "comments": [
            ...         {"text": "Where can I buy it?", "likes": 15},
            ...         {"text": "Looks great!", "likes": 5}
            ...     ]
            ... }
            >>> result = preprocessor.preprocess(input_data)
            >>> result.stats['has_transcription']
            True
        """
        # Extract fields from input
        content = input_data.get("content", {})
        caption = content.get("text", "")
        transcription = content.get("transcription", "")
        comments = input_data.get("comments", [])

        # Track source lengths for breakdown
        caption_len = len(caption) if caption else 0
        transcript_len = len(transcription) if transcription else 0
        comments_len = sum(len(c.get("text", "")) for c in comments[: self.max_comments])

        # Step 1: Merge content
        merged_text = self.merge_content(
            caption=caption, comments=comments, transcription=transcription
        )

        # Step 2: Normalize text
        clean_text = self.normalize(merged_text)

        # Step 3: Calculate statistics
        has_transcription = bool(transcription and transcription.strip())
        stats = self.calculate_stats(
            original_text=merged_text, clean_text=clean_text, has_transcription=has_transcription
        )

        # Step 4: Build source breakdown
        source_breakdown = {
            "caption_len": caption_len,
            "transcript_len": transcript_len,
            "comments_len": comments_len,
        }

        # Return result
        return PreprocessingResult(
            clean_text=clean_text, stats=stats, source_breakdown=source_breakdown
        )
