"""Sentiment Analysis use case.

This module implements aspect-based sentiment analysis (ABSA) using PhoBERT ONNX:
1. Overall sentiment for full text
2. Aspect-based sentiment using context windowing technique
3. Weighted aggregation for multiple mentions of same aspect
"""

from typing import Optional

from pkg.logger.logger import Logger
from pkg.phobert_onnx.phobert_onnx import PhoBERTONNX
from internal.sentiment_analysis.interface import ISentimentAnalysis
from internal.sentiment_analysis.type import *
from internal.sentiment_analysis.constant import *


class SentimentAnalysis(ISentimentAnalysis):
    """Aspect-Based Sentiment Analyzer using PhoBERT ONNX."""

    def __init__(
        self,
        config: Config,
        phobert_model: PhoBERTONNX,
        logger: Optional[Logger] = None,
    ):
        """Initialize sentiment analysis use case.

        Args:
            config: Configuration for sentiment analysis
            phobert_model: PhoBERT ONNX model instance
            logger: Logger instance (optional). If None, no logging will be performed.
        """
        self.config = config
        self.phobert_model = phobert_model
        self.logger = logger

        if self.logger:
            self.logger.info(
                "[SentimentAnalysis] Initialized",
                extra={
                    "context_window_size": self.config.context_window_size,
                    "threshold_positive": self.config.threshold_positive,
                    "threshold_negative": self.config.threshold_negative,
                },
            )

    def process(self, input_data: Input) -> Output:
        """Process input data and return output.

        Args:
            input_data: Input structure with text and optional keywords

        Returns:
            Output with overall and aspect-level sentiments

        Raises:
            ValueError: If input_data is invalid
            Exception: If processing fails
        """
        if not isinstance(input_data, Input):
            error_msg = "input_data must be an instance of Input"
            if self.logger:
                self.logger.error(
                    "[SentimentAnalysis] Invalid input type",
                    extra={"input_type": type(input_data).__name__},
                )
            raise ValueError(error_msg)

        try:
            text = input_data.text
            keywords = input_data.keywords

            if self.logger:
                self.logger.debug(
                    "[SentimentAnalysis] Processing started",
                    extra={
                        "text_len": len(text),
                        "keywords_count": len(keywords),
                    },
                )

            # Handle empty text
            if not text or not text.strip():
                if self.logger:
                    self.logger.warn(
                        "[SentimentAnalysis] Empty text, returning neutral sentiment"
                    )
                return Output(
                    overall=SentimentResult(
                        label=LABEL_NEUTRAL,
                        score=0.0,
                        confidence=0.0,
                        probabilities={},
                    ),
                    aspects={},
                )

            # Analyze overall sentiment
            overall_sentiment = self._analyze_overall(text)

            # Analyze aspect-based sentiment if keywords provided
            aspect_sentiments = {}
            if keywords:
                # Filter valid keywords
                valid_keywords = [
                    kw for kw in keywords if kw.keyword and kw.keyword.strip()
                ]

                if valid_keywords:
                    aspect_sentiments = self._analyze_aspects(text, valid_keywords)
                else:
                    if self.logger:
                        self.logger.debug(
                            "[SentimentAnalysis] No valid keywords, skipping aspect analysis"
                        )
            else:
                if self.logger:
                    self.logger.debug(
                        "[SentimentAnalysis] No keywords provided, overall sentiment only"
                    )

            if self.logger:
                self.logger.info(
                    "[SentimentAnalysis] Processing completed",
                    extra={
                        "overall_label": overall_sentiment.label,
                        "aspects_count": len(aspect_sentiments),
                    },
                )

            return Output(overall=overall_sentiment, aspects=aspect_sentiments)

        except ValueError:
            raise
        except Exception as e:
            if self.logger:
                self.logger.error(
                    "[SentimentAnalysis] Processing failed",
                    extra={"error": str(e), "error_type": type(e).__name__},
                )
            raise

    def _analyze_overall(self, text: str) -> SentimentResult:
        """Analyze overall sentiment for full text."""
        try:
            # Use PhoBERT to predict sentiment
            phobert_result = self.phobert_model.predict(text, return_probabilities=True)

            # Convert to ABSA format
            return self._convert_to_absa_format(phobert_result)

        except Exception as e:
            if self.logger:
                self.logger.warn(
                    "[SentimentAnalysis] PhoBERT prediction failed for overall sentiment",
                    extra={"error": str(e)},
                )

            # Graceful degradation
            return SentimentResult(
                label=LABEL_NEUTRAL,
                score=0.0,
                confidence=0.0,
                probabilities={},
                error=str(e),
            )

    def _analyze_aspects(
        self, text: str, keywords: list[KeywordInput]
    ) -> dict[str, AspectSentiment]:
        """Analyze sentiment for each aspect using context windowing."""
        # Group keywords by aspect
        grouped_keywords = self._group_keywords_by_aspect(keywords)

        aspect_results: dict[str, AspectSentiment] = {}

        # Analyze each aspect
        for aspect, aspect_keywords in grouped_keywords.items():
            sentiment_results = []
            failed_keywords = []

            # Analyze each keyword mention
            for kw_data in aspect_keywords:
                keyword = kw_data.keyword
                position = kw_data.position

                try:
                    # Extract context window
                    context = self._extract_smart_window(text, keyword, position)

                    # Skip if context too short
                    if not context or len(context) < len(keyword):
                        if self.logger:
                            self.logger.debug(
                                f"[SentimentAnalysis] Context too short for keyword '{keyword}'"
                            )
                        failed_keywords.append(keyword)
                        continue

                    # Predict sentiment
                    phobert_result = self.phobert_model.predict(
                        context, return_probabilities=False
                    )

                    # Convert to ABSA format
                    result = self._convert_to_absa_format(phobert_result)

                    # Add keyword for aggregation
                    sentiment_results.append(
                        {
                            "keyword": keyword,
                            "label": result.label,
                            "score": result.score,
                            "confidence": result.confidence,
                            "rating": result.rating,
                        }
                    )

                except Exception as e:
                    if self.logger:
                        self.logger.warn(
                            f"[SentimentAnalysis] Failed to analyze keyword '{keyword}'",
                            extra={"aspect": aspect, "error": str(e)},
                        )
                    failed_keywords.append(keyword)
                    continue

            # Aggregate results
            if sentiment_results:
                aspect_results[aspect] = self._aggregate_scores(sentiment_results)
            else:
                if self.logger:
                    self.logger.info(
                        f"[SentimentAnalysis] No valid results for aspect {aspect}",
                        extra={"failed_keywords": failed_keywords},
                    )
                aspect_results[aspect] = AspectSentiment(
                    label=LABEL_NEUTRAL,
                    score=0.0,
                    confidence=0.0,
                    mentions=len(aspect_keywords),
                    keywords=[kw.keyword for kw in aspect_keywords],
                    rating=DEFAULT_RATING,
                )

        return aspect_results

    def _extract_smart_window(
        self, text: str, keyword: str, position: int | None = None
    ) -> str:
        """Extract context window around keyword with smart boundary snapping."""
        # Handle empty inputs
        if not text or not text.strip():
            return ""

        if not keyword or not keyword.strip():
            return text

        # Find keyword position if not provided
        if position is None:
            keyword_lower = keyword.lower()
            text_lower = text.lower()
            position = text_lower.find(keyword_lower)

            if position == -1:
                return text

        # Validate position
        if position < 0 or position >= len(text):
            return text

        radius = self.config.context_window_size
        text_len = len(text)

        # Initial coarse window
        start = max(0, position - radius)
        end = min(text_len, position + len(keyword) + radius)

        snippet = text[start:end]
        kw_start_in_snippet = position - start
        kw_end_in_snippet = kw_start_in_snippet + len(keyword)

        # Cut on the left: find nearest delimiter BEFORE keyword
        left_part = snippet[:kw_start_in_snippet]
        best_left_cut = -1
        for delim in DELIMITERS:
            idx = left_part.rfind(delim)
            if idx != -1 and idx > best_left_cut:
                best_left_cut = idx + len(delim)

        if best_left_cut != -1:
            start = start + best_left_cut

        # Recompute snippet after left cut
        snippet = text[start:end]
        kw_start_in_snippet = position - start
        kw_end_in_snippet = kw_start_in_snippet + len(keyword)

        # Cut on the right: find nearest delimiter AFTER keyword
        right_part = snippet[kw_end_in_snippet:]
        best_right_cut = None
        for delim in DELIMITERS:
            idx = right_part.find(delim)
            if idx != -1:
                if best_right_cut is None or idx < best_right_cut:
                    best_right_cut = idx

        if best_right_cut is not None:
            end = position + len(keyword) + best_right_cut

        # Snap to word boundaries
        while start > 0 and start < text_len and text[start] not in WHITESPACE_CHARS:
            start -= 1
        while end < text_len and text[end] not in WHITESPACE_CHARS:
            end += 1

        context = text[start:end].strip(STRIP_PUNCTUATION)

        # Fallback if context too short
        return context if context and len(context) >= len(keyword) else text

    def _aggregate_scores(
        self, results: list[dict]
    ) -> AspectSentiment:
        """Aggregate multiple sentiment results using weighted average."""
        if not results:
            return AspectSentiment(
                label=LABEL_NEUTRAL,
                score=0.0,
                confidence=0.0,
                mentions=0,
                keywords=[],
                rating=DEFAULT_RATING,
            )

        if len(results) == 1:
            result = results[0]
            return AspectSentiment(
                label=result["label"],
                score=result["score"],
                confidence=result["confidence"],
                mentions=1,
                keywords=[result["keyword"]],
                rating=result.get("rating", DEFAULT_RATING),
            )

        # Multiple mentions - weighted average by confidence
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

        # Calculate weighted average
        if total_confidence > 0:
            avg_score = total_weighted_score / total_confidence
        else:
            avg_score = 0.0

        # Map score to label
        label = self._map_score_to_label(avg_score)

        # Average rating
        ratings = [r.get("rating", DEFAULT_RATING) for r in results]
        avg_rating = round(sum(ratings) / len(ratings)) if ratings else DEFAULT_RATING

        # Average confidence
        avg_confidence = total_confidence / len(results) if results else 0.0

        return AspectSentiment(
            label=label,
            score=round(avg_score, 3),
            confidence=round(avg_confidence, 3),
            mentions=len(results),
            keywords=keywords,
            rating=avg_rating,
        )

    def _convert_to_absa_format(self, phobert_result: dict) -> SentimentResult:
        """Convert PhoBERT 5-class result to 3-class ABSA format."""
        # Get rating (1-5)
        rating = phobert_result.get("rating", DEFAULT_RATING)

        # Map rating to score
        score_map = {
            1: SCORE_RATING_1,
            2: SCORE_RATING_2,
            3: SCORE_RATING_3,
            4: SCORE_RATING_4,
            5: SCORE_RATING_5,
        }
        score = score_map.get(rating, SCORE_RATING_3)

        # Map score to label
        label = self._map_score_to_label(score)

        return SentimentResult(
            label=label,
            score=score,
            confidence=phobert_result.get("confidence", 0.0),
            probabilities=phobert_result.get("probabilities", {}),
            rating=rating,
        )

    def _group_keywords_by_aspect(
        self, keywords: list[KeywordInput]
    ) -> dict[str, list[KeywordInput]]:
        """Group keywords by aspect label."""
        grouped: dict[str, list[KeywordInput]] = {}

        for keyword in keywords:
            aspect = keyword.aspect

            if aspect not in grouped:
                grouped[aspect] = []

            grouped[aspect].append(keyword)

        return grouped

    def _map_score_to_label(self, score: float) -> str:
        """Map numeric score to sentiment label using thresholds."""
        if score > self.config.threshold_positive:
            return LABEL_POSITIVE
        elif score < self.config.threshold_negative:
            return LABEL_NEGATIVE
        else:
            return LABEL_NEUTRAL


__all__ = ["SentimentAnalysis"]
