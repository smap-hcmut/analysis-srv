from typing import Optional

from pkg.logger.logger import Logger
from pkg.phobert_onnx.phobert_onnx import PhoBERTONNX
from internal.sentiment_analysis.interface import ISentimentAnalysisUseCase
from internal.sentiment_analysis.type import Config, Input, Output
from .process import process as _process


class SentimentAnalysisUseCase(ISentimentAnalysisUseCase):
    def __init__(
        self,
        config: Config,
        phobert_model: PhoBERTONNX,
        logger: Optional[Logger] = None,
    ):
        self.config = config
        self.phobert_model = phobert_model
        self.logger = logger

    def process(self, input_data: Input) -> Output:
        return _process(
            input_data=input_data,
            phobert_model=self.phobert_model,
            config=self.config,
            logger=self.logger,
        )
