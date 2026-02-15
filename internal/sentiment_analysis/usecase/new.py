from typing import Optional

from pkg.logger.logger import Logger
from pkg.phobert_onnx.phobert_onnx import PhoBERTONNX
from internal.sentiment_analysis.type import Config
from .sentiment_analysis import SentimentAnalysis


def New(
    config: Config, phobert_model: PhoBERTONNX, logger: Optional[Logger] = None
) -> SentimentAnalysis:
    """Create new SentimentAnalysis instance.

    Args:
        config: Configuration for sentiment analysis
        phobert_model: PhoBERT ONNX model instance
        logger: Logger instance (optional, for logging)

    Returns:
        SentimentAnalysis instance

    Raises:
        ValueError: If config or phobert_model is invalid
    """
    if not isinstance(config, Config):
        raise ValueError("config must be an instance of Config")

    if not isinstance(phobert_model, PhoBERTONNX):
        raise ValueError("phobert_model must be an instance of PhoBERTONNX")

    return SentimentAnalysis(config, phobert_model, logger)


__all__ = ["New"]
