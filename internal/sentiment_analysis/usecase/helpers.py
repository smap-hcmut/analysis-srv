import unicodedata
from typing import List, Dict, Optional, Any

from pkg.logger.logger import Logger
from pkg.phobert_onnx.phobert_onnx import PhoBERTONNX
from internal.sentiment_analysis.type import (
    Config,
    KeywordInput,
    SentimentResult,
    AspectSentiment,
)
from internal.sentiment_analysis.constant import (
    LABEL_NEUTRAL,
    LABEL_POSITIVE,
    LABEL_NEGATIVE,
    DEFAULT_RATING,
    SCORE_RATING_1,
    SCORE_RATING_2,
    SCORE_RATING_3,
    SCORE_RATING_4,
    SCORE_RATING_5,
    DELIMITERS,
    WHITESPACE_CHARS,
    STRIP_PUNCTUATION,
)


def map_score_to_label(score: float, config: Config) -> str:
    if score > config.threshold_positive:
        return LABEL_POSITIVE
    elif score < config.threshold_negative:
        return LABEL_NEGATIVE
    else:
        return LABEL_NEUTRAL


def convert_to_absa_format(phobert_result: dict, config: Config) -> SentimentResult:
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
    label = map_score_to_label(score, config)

    return SentimentResult(
        label=label,
        score=score,
        confidence=phobert_result.get("confidence", 0.0),
        probabilities=phobert_result.get("probabilities", {}),
        rating=rating,
    )


def extract_smart_window(
    text: str, keyword: str, context_window_size: int, position: Optional[int] = None
) -> str:
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

    radius = context_window_size
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


def aggregate_scores(results: list[dict], config: Config) -> AspectSentiment:
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
    label = map_score_to_label(avg_score, config)

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


def group_keywords_by_aspect(
    keywords: list[KeywordInput],
) -> dict[str, list[KeywordInput]]:
    grouped: dict[str, list[KeywordInput]] = {}

    for keyword in keywords:
        aspect = keyword.aspect

        if aspect not in grouped:
            grouped[aspect] = []

        grouped[aspect].append(keyword)

    return grouped


def analyze_overall(
    text: str,
    phobert_model: PhoBERTONNX,
    config: Config,
    logger: Optional[Logger] = None,
) -> SentimentResult:
    try:
        # Use PhoBERT to predict sentiment
        phobert_result = phobert_model.predict(text, return_probabilities=True)

        # Convert to ABSA format
        return convert_to_absa_format(phobert_result, config)

    except Exception as e:
        if logger:
            logger.warn(
                "PhoBERT prediction failed for overall sentiment",
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


def analyze_aspects(
    text: str,
    keywords: list[KeywordInput],
    phobert_model: PhoBERTONNX,
    config: Config,
    logger: Optional[Logger] = None,
) -> dict[str, AspectSentiment]:
    # Group keywords by aspect
    grouped_keywords = group_keywords_by_aspect(keywords)

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
                context = extract_smart_window(
                    text=text,
                    keyword=keyword,
                    context_window_size=config.context_window_size,
                    position=position,
                )

                # Skip if context too short
                if not context or len(context) < len(keyword):
                    if logger:
                        logger.debug(f"Context too short for keyword '{keyword}'")
                    failed_keywords.append(keyword)
                    continue

                # Predict sentiment
                phobert_result = phobert_model.predict(
                    context, return_probabilities=False
                )

                # Convert to ABSA format
                result = convert_to_absa_format(phobert_result, config)

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
                logger.warn(
                    f"Failed to analyze keyword '{keyword}'",
                    extra={"aspect": aspect, "error": str(e)},
                )
                failed_keywords.append(keyword)
                continue

        # Aggregate results
        if sentiment_results:
            aspect_results[aspect] = aggregate_scores(sentiment_results, config)
        else:
            if logger:
                logger.info(
                    f"No valid results for aspect {aspect}",
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
