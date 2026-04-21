from typing import Optional, List, Dict, Tuple

from pkg.logger.logger import Logger
from pkg.phobert_onnx.phobert_onnx import PhoBERTONNX
from internal.sentiment_analysis.type import (
    Input,
    Output,
    SentimentResult,
    AspectSentiment,
    Config,
)
from internal.sentiment_analysis.constant import LABEL_NEUTRAL, DEFAULT_RATING
from .helpers import (
    analyze_overall,
    analyze_overall_batch,
    analyze_aspects,
    convert_to_absa_format,
    extract_smart_window,
    aggregate_scores,
    group_keywords_by_aspect,
)


def process(
    input_data: Input,
    phobert_model: PhoBERTONNX,
    config: Config,
    logger: Optional[Logger] = None,
) -> Output:
    try:
        text = input_data.text
        keywords = input_data.keywords

        logger.debug(
            "internal.sentiment_analysis.usecase.process: Processing started",
            extra={"text_len": len(text), "keywords_count": len(keywords)},
        )

        # Handle empty text
        if not text or not text.strip():
            logger.debug(
                "internal.sentiment_analysis.usecase.process: Empty text, returning neutral sentiment"
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
        overall_sentiment = analyze_overall(text, phobert_model, config, logger)

        # Analyze aspect-based sentiment if keywords provided
        aspect_sentiments = {}
        if keywords:
            # Filter valid keywords
            valid_keywords = [
                kw for kw in keywords if kw.keyword and kw.keyword.strip()
            ]

            if valid_keywords:
                aspect_sentiments = analyze_aspects(
                    text, valid_keywords, phobert_model, config, logger
                )
            else:
                logger.debug(
                    "internal.sentiment_analysis.usecase.process: No valid keywords, skipping aspect analysis"
                )
        else:
            logger.debug(
                "internal.sentiment_analysis.usecase.process: No keywords provided, overall sentiment only"
            )

        logger.info(
            "internal.sentiment_analysis.usecase.process: Processing completed",
            extra={
                "overall_label": overall_sentiment.label,
                "aspects_count": len(aspect_sentiments),
            },
        )

        return Output(overall=overall_sentiment, aspects=aspect_sentiments)

    except ValueError:
        raise
    except Exception as e:
        logger.error("internal.sentiment_analysis.usecase.process: %s", e)
        raise


def process_batch(
    input_list: List[Input],
    phobert_model: PhoBERTONNX,
    config: Config,
    logger: Optional[Logger] = None,
) -> List[Output]:
    """Batch sentiment analysis — two ONNX calls total for N inputs.

    Phase 1: batch predict overall sentiment for all N texts (1 ONNX call).
    Phase 2: collect all keyword context windows from all N inputs, batch
             predict in a single ONNX call, then aggregate per aspect/record.

    Args:
        input_list: List of Input objects (text + keywords per record)
        phobert_model: PhoBERT model wrapper
        config: Sentiment analysis configuration
        logger: Optional logger

    Returns:
        List of Output objects, one per input (preserves order)
    """
    if not input_list:
        return []

    # --- Phase 1: batch overall sentiment (1 ONNX call) ---
    texts = [inp.text for inp in input_list]
    overall_results = analyze_overall_batch(texts, phobert_model, config, logger)

    # --- Phase 2: collect ALL keyword context windows across all inputs ---
    # Each entry: (orig_input_idx, aspect, keyword_str, context_text)
    all_context_meta: List[Tuple[int, str, str, str]] = []
    for i, inp in enumerate(input_list):
        if not inp.text or not inp.text.strip() or not inp.keywords:
            continue
        valid_kws = [kw for kw in inp.keywords if kw.keyword and kw.keyword.strip()]
        for kw in valid_kws:
            context = extract_smart_window(
                text=inp.text,
                keyword=kw.keyword,
                context_window_size=config.context_window_size,
                position=kw.position,
            )
            if context and len(context) >= len(kw.keyword):
                all_context_meta.append((i, kw.aspect, kw.keyword, context))

    # Batch predict all keyword contexts (1 ONNX call for all records × keywords)
    # {orig_input_idx: {aspect: [{keyword, label, score, confidence, rating}]}}
    aspect_score_map: Dict[int, Dict[str, List[dict]]] = {}
    if all_context_meta:
        context_texts = [m[3] for m in all_context_meta]
        try:
            context_preds = phobert_model.predict_batch(
                context_texts, return_probabilities=False
            )
        except Exception as exc:
            if logger:
                logger.warn(
                    "PhoBERT batch context prediction failed",
                    extra={"error": str(exc), "count": len(context_texts)},
                )
            context_preds = [None] * len(context_texts)  # type: ignore[list-item]

        for (orig_idx, aspect, kw_str, _), pred in zip(all_context_meta, context_preds):
            if pred is None:
                continue
            absa = convert_to_absa_format(pred, config)
            aspect_score_map.setdefault(orig_idx, {}).setdefault(aspect, []).append(
                {
                    "keyword": kw_str,
                    "label": absa.label,
                    "score": absa.score,
                    "confidence": absa.confidence,
                    "rating": absa.rating,
                }
            )

    # --- Build Output per input ---
    outputs: List[Output] = []
    for i, (inp, overall) in enumerate(zip(input_list, overall_results)):
        aspect_sentiments = {}

        # Aggregate scores for aspects that had valid context windows
        for aspect, kw_scores in aspect_score_map.get(i, {}).items():
            aspect_sentiments[aspect] = aggregate_scores(kw_scores, config)

        # Aspects whose every keyword failed context extraction → emit neutral
        if inp.keywords:
            valid_kws = [kw for kw in inp.keywords if kw.keyword and kw.keyword.strip()]
            for aspect, kws in group_keywords_by_aspect(valid_kws).items():
                if aspect not in aspect_sentiments:
                    aspect_sentiments[aspect] = AspectSentiment(
                        label=LABEL_NEUTRAL,
                        score=0.0,
                        confidence=0.0,
                        mentions=len(kws),
                        keywords=[kw.keyword for kw in kws],
                        rating=DEFAULT_RATING,
                    )

        outputs.append(Output(overall=overall, aspects=aspect_sentiments))

    return outputs
