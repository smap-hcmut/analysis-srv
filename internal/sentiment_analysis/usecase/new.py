from typing import Optional

from pkg.logger.logger import Logger
from pkg.phobert_onnx.phobert_onnx import PhoBERTONNX
from internal.sentiment_analysis.interface import ISentimentAnalysisUseCase
from internal.sentiment_analysis.type import Config
from .usecase import SentimentAnalysisUseCase


def New(
    config: Config,
    phobert_model: PhoBERTONNX,
    logger: Optional[Logger] = None,
) -> ISentimentAnalysisUseCase:
    return SentimentAnalysisUseCase(
        config=config, phobert_model=phobert_model, logger=logger
    )


__all__ = ["New"]
