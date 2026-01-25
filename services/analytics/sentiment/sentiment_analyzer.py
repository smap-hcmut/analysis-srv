"""Aspect-Based Sentiment Analyzer (ABSA) using PhoBERT ONNX.

This module implements sentiment analysis with:
1. Overall sentiment for full text
2. Aspect-based sentiment using context windowing technique
3. Weighted aggregation for multiple mentions of same aspect
"""

import logging
from typing import Dict, List, Any, Optional

from infrastructure.ai import PhoBERTONNX
from infrastructure.ai.constants import (
    DEFAULT_CONTEXT_WINDOW_SIZE,
    THRESHOLD_POSITIVE,
    THRESHOLD_NEGATIVE,
    SCORE_MAP,
    ABSA_LABELS,
)

# Configure logger
logger = logging.getLogger(__name__)


class SentimentAnalyzer:
    """Aspect-Based Sentiment Analyzer using PhoBERT ONNX.

    This class provides both overall and aspect-level sentiment analysis
    by combining PhoBERT predictions with context windowing technique.

    Attributes:
        phobert_model: PhoBERT ONNX model instance for sentiment prediction
        context_window_size: Size of context window (characters) around keywords
        threshold_positive: Score threshold for positive sentiment
        threshold_negative: Score threshold for negative sentiment

    Example:
        >>> analyzer = SentimentAnalyzer(phobert_model)
        >>> keywords = [
        ...     {"keyword": "thiết kế", "aspect": "DESIGN", "position": 3},
        ...     {"keyword": "giá", "aspect": "PRICE", "position": 20}
        ... ]
        >>> result = analyzer.analyze("Xe thiết kế đẹp nhưng giá quá đắt", keywords)
        >>> print(result)
        {
            "overall": {
                "label": "NEUTRAL",
                "score": 0.0,
                "confidence": 0.65,
                "probabilities": {...}
            },
            "aspects": {
                "DESIGN": {
                    "label": "POSITIVE",
                    "score": 1.0,
                    "confidence": 0.92,
                    "mentions": 1,
                    "keywords": ["thiết kế"]
                },
                "PRICE": {
                    "label": "NEGATIVE",
                    "score": -1.0,
                    "confidence": 0.88,
                    "mentions": 1,
                    "keywords": ["giá"]
                }
            }
        }
    """

    def __init__(
        self,
        phobert_model: PhoBERTONNX,
        context_window_size: int = DEFAULT_CONTEXT_WINDOW_SIZE,
        threshold_positive: float = THRESHOLD_POSITIVE,
        threshold_negative: float = THRESHOLD_NEGATIVE,
    ):
        """Initialize SentimentAnalyzer.

        Args:
            phobert_model: PhoBERT ONNX model instance
            context_window_size: Size of context window (characters) around keywords
            threshold_positive: Score threshold for positive sentiment (default: 0.25)
            threshold_negative: Score threshold for negative sentiment (default: -0.25)
        """
        self.phobert_model = phobert_model
        self.context_window_size = context_window_size
        self.threshold_positive = threshold_positive
        self.threshold_negative = threshold_negative

    def analyze(self, text: str, keywords: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """Analyze sentiment for both overall text and specific aspects.

        Args:
            text: Input text (preprocessed Vietnamese text)
            keywords: Optional list of keywords with aspect labels from KeywordExtractor
                Each keyword dict should contain:
                - keyword (str): The extracted keyword
                - aspect (str): Business aspect (DESIGN, PERFORMANCE, PRICE, SERVICE, GENERAL)
                - score (float): Extraction confidence score
                - source (str): DICT or AI

        Returns:
            Dictionary containing:
                - overall: Overall sentiment analysis for full text
                - aspects: Aspect-level sentiment analysis (empty dict if no keywords)

        Note:
            - Empty text returns neutral sentiment with 0 confidence
            - Empty/missing keywords returns overall sentiment only
            - Missing aspect in keywords defaults to "GENERAL"
        """
        # Handle empty text - return neutral sentiment
        if not text or not text.strip():
            logger.warning("Empty text provided to analyze(). Returning neutral sentiment.")
            return {
                "overall": {
                    "label": ABSA_LABELS["NEUTRAL"],
                    "score": 0.0,
                    "confidence": 0.0,
                    "probabilities": {},
                },
                "aspects": {},
            }

        # Analyze overall sentiment for full text
        overall_sentiment = self._analyze_overall(text)

        # Analyze aspect-based sentiment if keywords provided
        aspect_sentiments = {}
        if keywords and len(keywords) > 0:
            # Filter out invalid keywords (missing required fields)
            valid_keywords = [kw for kw in keywords if isinstance(kw, dict) and kw.get("keyword")]

            if valid_keywords:
                aspect_sentiments = self._analyze_aspects(text, valid_keywords)
            else:
                logger.debug("No valid keywords provided. Skipping aspect analysis.")
        else:
            logger.debug("No keywords provided. Returning overall sentiment only.")

        return {
            "overall": overall_sentiment,
            "aspects": aspect_sentiments,
        }

    def _analyze_overall(self, text: str) -> Dict[str, Any]:
        """Analyze overall sentiment for full text.

        Args:
            text: Input text

        Returns:
            Dictionary with label, score, confidence, probabilities

        Note:
            - Returns neutral sentiment with 0 confidence on prediction failure
            - Logs warnings for debugging when errors occur
        """
        try:
            # Use PhoBERT to predict sentiment for full text
            phobert_result = self.phobert_model.predict(text, return_probabilities=True)

            # Convert 5-class result to 3-class ABSA format
            absa_result = self._convert_to_absa_format(phobert_result)

            return absa_result

        except Exception as e:
            # Log error for debugging
            logger.warning(
                f"PhoBERT prediction failed for overall sentiment: {str(e)}. "
                f"Returning neutral sentiment as fallback."
            )

            # Graceful degradation: return neutral sentiment with low confidence
            return {
                "label": ABSA_LABELS["NEUTRAL"],
                "score": 0.0,
                "confidence": 0.0,
                "probabilities": {},
                "error": str(e),
            }

    def _analyze_aspects(
        self, text: str, keywords: List[Dict[str, Any]]
    ) -> Dict[str, Dict[str, Any]]:
        """Analyze sentiment for each aspect using context windowing.

        Args:
            text: Input text
            keywords: List of keywords with aspect labels

        Returns:
            Dictionary mapping aspect to sentiment results

        Note:
            - Gracefully handles prediction failures for individual keywords
            - Uses overall sentiment as fallback if all keywords fail
            - Logs warnings when keywords are skipped due to errors
        """
        # Group keywords by aspect
        grouped_keywords = self._group_keywords_by_aspect(keywords)

        aspect_results: Dict[str, Dict[str, Any]] = {}

        # Analyze each aspect
        for aspect, aspect_keywords in grouped_keywords.items():
            sentiment_results = []
            failed_keywords = []

            # Analyze each keyword mention for this aspect
            for kw_data in aspect_keywords:
                keyword = kw_data.get("keyword", "")
                position = kw_data.get("position", None)

                # Skip empty keywords
                if not keyword:
                    continue

                try:
                    # Extract context window around keyword
                    context = self._extract_smart_window(text, keyword, position)

                    # Skip if context is too short (less than keyword itself)
                    if not context or len(context) < len(keyword):
                        logger.debug(
                            f"Skipping keyword '{keyword}' for aspect {aspect}: "
                            f"context too short ({len(context)} chars)"
                        )
                        failed_keywords.append(keyword)
                        continue

                    # Predict sentiment for context
                    phobert_result = self.phobert_model.predict(context, return_probabilities=False)

                    # Convert to ABSA format
                    absa_result = self._convert_to_absa_format(phobert_result)

                    # Add keyword to result for aggregation
                    absa_result["keyword"] = keyword

                    sentiment_results.append(absa_result)

                except Exception as e:
                    # Log error but continue processing other keywords
                    logger.warning(
                        f"Failed to analyze sentiment for keyword '{keyword}' "
                        f"in aspect {aspect}: {str(e)}"
                    )
                    failed_keywords.append(keyword)
                    continue

            # Aggregate results for this aspect
            if sentiment_results:
                aspect_results[aspect] = self._aggregate_scores(sentiment_results)
            else:
                # No valid results - use neutral sentiment
                logger.info(
                    f"No valid sentiment results for aspect {aspect}. "
                    f"Failed keywords: {failed_keywords}. Using neutral sentiment."
                )
                aspect_results[aspect] = {
                    "label": ABSA_LABELS["NEUTRAL"],
                    "score": 0.0,
                    "rating": 3,  # Neutral rating
                    "confidence": 0.0,
                    "mentions": len(aspect_keywords),
                    "keywords": [kw.get("keyword", "") for kw in aspect_keywords],
                }

        return aspect_results

    def _extract_smart_window(self, text: str, keyword: str, position: Optional[int] = None) -> str:
        """Extract context window around keyword with smart boundary snapping.

        This implementation:
        - Uses a configurable radius around the keyword
        - Then trims the window to nearby delimiters (punctuation and pivot words like "nhưng")
        - Finally snaps to word boundaries to avoid cutting inside tokens
        """
        # Edge case: empty or invalid inputs
        if not text or not text.strip():
            return ""

        if not keyword or not keyword.strip():
            return text

        # Find keyword position if not provided
        if position is None:
            keyword_lower = keyword.lower()
            text_lower = text.lower()
            position = text_lower.find(keyword_lower)

            # Keyword not found in text - return full text as fallback
            if position == -1:
                return text

        # Edge case: position is invalid
        if position < 0 or position >= len(text):
            return text

        radius = self.context_window_size
        text_len = len(text)

        # Initial coarse window
        start = max(0, position - radius)
        end = min(text_len, position + len(keyword) + radius)

        snippet = text[start:end]
        kw_start_in_snippet = position - start
        kw_end_in_snippet = kw_start_in_snippet + len(keyword)

        # Delimiters and pivot words that break clauses / sentiments
        delimiters = [".", ",", ";", "!", "?", "nhưng", "tuy nhiên", "mặc dù", "bù lại"]

        # Cut on the left: find nearest delimiter BEFORE the keyword
        left_part = snippet[:kw_start_in_snippet]
        best_left_cut = -1
        for delim in delimiters:
            idx = left_part.rfind(delim)
            if idx != -1 and idx > best_left_cut:
                best_left_cut = idx + len(delim)

        if best_left_cut != -1:
            start = start + best_left_cut

        # Recompute snippet after left cut
        snippet = text[start:end]
        kw_start_in_snippet = position - start
        kw_end_in_snippet = kw_start_in_snippet + len(keyword)

        # Cut on the right: find nearest delimiter AFTER the keyword
        right_part = snippet[kw_end_in_snippet:]
        best_right_cut = None
        for delim in delimiters:
            idx = right_part.find(delim)
            if idx != -1:
                if best_right_cut is None or idx < best_right_cut:
                    best_right_cut = idx

        if best_right_cut is not None:
            end = position + len(keyword) + best_right_cut

        # Snap to word boundaries to avoid cutting inside tokens
        while start > 0 and start < text_len and text[start] not in " \t\n":
            start -= 1
        while end < text_len and text[end] not in " \t\n":
            end += 1

        context = text[start:end].strip(" \n\t.,;!?")

        # Final fallback: if context is empty or too short, return full text
        return context if context and len(context) >= len(keyword) else text

    def _aggregate_scores(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Aggregate multiple sentiment results using weighted average.

        Args:
            results: List of sentiment results for same aspect
                Each result should contain: score, confidence, keyword

        Returns:
            Aggregated sentiment with label, score, confidence, mentions, keywords
        """
        if not results:
            return {
                "label": ABSA_LABELS["NEUTRAL"],
                "score": 0.0,
                "rating": 3,  # Neutral rating
                "confidence": 0.0,
                "mentions": 0,
                "keywords": [],
            }

        if len(results) == 1:
            # Single mention - no aggregation needed
            result = results[0]
            return {
                "label": result["label"],
                "score": result["score"],
                "rating": result.get("rating", 3),  # Keep rating for backward compatibility
                "confidence": result["confidence"],
                "mentions": 1,
                "keywords": [result["keyword"]],
            }

        # Multiple mentions - use weighted average by confidence
        total_weighted_score = 0.0
        total_confidence = 0.0
        keywords = []

        for result in results:
            score = result.get("score", 0.0)
            confidence = result.get("confidence", 0.0)
            keyword = result.get("keyword", "")

            total_weighted_score += score * confidence
            total_confidence += confidence
            keywords.append(keyword)

        # Calculate weighted average score
        if total_confidence > 0:
            avg_score = total_weighted_score / total_confidence
        else:
            avg_score = 0.0

        # Map aggregated score to label
        label = self._map_score_to_label(avg_score)

        # Calculate aggregated rating (average of ratings, rounded)
        ratings = [r.get("rating", 3) for r in results]
        avg_rating = round(sum(ratings) / len(ratings)) if ratings else 3

        # Use average confidence
        avg_confidence = total_confidence / len(results) if results else 0.0

        return {
            "label": label,
            "score": round(avg_score, 3),
            "rating": avg_rating,  # Keep rating for backward compatibility
            "confidence": round(avg_confidence, 3),
            "mentions": len(results),
            "keywords": keywords,
        }

    def _convert_to_absa_format(self, phobert_result: Dict[str, Any]) -> Dict[str, Any]:
        """Convert PhoBERT 5-class result to 3-class ABSA format.

        Args:
            phobert_result: Result from PhoBERT.predict()
                Contains: rating, sentiment, confidence, probabilities

        Returns:
            Dictionary with:
                - label: POSITIVE, NEGATIVE, or NEUTRAL
                - score: Numeric score (-1.0 to 1.0)
                - confidence: Model confidence (0-1)
                - probabilities: Original 5-class probabilities
        """
        # Get rating (1-5) from PhoBERT result
        rating = phobert_result.get("rating", 3)

        # Map rating to numeric score using SCORE_MAP
        score = SCORE_MAP.get(rating, 0.0)

        # Map score to 3-class label
        label = self._map_score_to_label(score)

        return {
            "label": label,
            "score": score,
            "rating": rating,  # Keep rating for backward compatibility with examples
            "confidence": phobert_result.get("confidence", 0.0),
            "probabilities": phobert_result.get("probabilities", {}),
        }

    def _group_keywords_by_aspect(
        self, keywords: List[Dict[str, Any]]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Group keywords by aspect label.

        Args:
            keywords: List of keywords with aspect labels

        Returns:
            Dictionary mapping aspect to list of keywords
        """
        grouped: Dict[str, List[Dict[str, Any]]] = {}

        for keyword in keywords:
            aspect = keyword.get("aspect", "GENERAL")

            if aspect not in grouped:
                grouped[aspect] = []

            grouped[aspect].append(keyword)

        return grouped

    def _map_score_to_label(self, score: float) -> str:
        """Map numeric score to sentiment label using thresholds.

        Args:
            score: Numeric sentiment score (-1.0 to 1.0)

        Returns:
            Sentiment label: POSITIVE, NEGATIVE, or NEUTRAL
        """
        if score > self.threshold_positive:
            return ABSA_LABELS["POSITIVE"]
        elif score < self.threshold_negative:
            return ABSA_LABELS["NEGATIVE"]
        else:
            return ABSA_LABELS["NEUTRAL"]
