from typing import Optional

from pkg.logger.logger import Logger
from pkg.phobert_onnx.phobert_onnx import PhoBERTONNX
from internal.sentiment_analysis.type import Input, Output, SentimentResult, Config
from internal.sentiment_analysis.constant import LABEL_NEUTRAL
from .helpers import analyze_overall, analyze_aspects


def process(
    input_data: Input,
    phobert_model: PhoBERTONNX,
    config: Config,
    logger: Optional[Logger] = None,
) -> Output:
    try:
        text = input_data.text
        keywords = input_data.keywords

        logger.debug("internal.sentiment_analysis.usecase.process: Processing started", extra={"text_len": len(text), "keywords_count": len(keywords)})

        # Handle empty text
        if not text or not text.strip():
            logger.warn("internal.sentiment_analysis.usecase.process: Empty text, returning neutral sentiment")
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
                logger.debug("internal.sentiment_analysis.usecase.process: No valid keywords, skipping aspect analysis")
        else:
            logger.debug("internal.sentiment_analysis.usecase.process: No keywords provided, overall sentiment only")

        logger.info("internal.sentiment_analysis.usecase.process: Processing completed", extra={"overall_label": overall_sentiment.label, "aspects_count": len(aspect_sentiments)})

        return Output(overall=overall_sentiment, aspects=aspect_sentiments)

    except ValueError:
        raise
    except Exception as e:
        logger.error("internal.sentiment_analysis.usecase.process: %s", e)
        raise
