from __future__ import annotations

from typing import Optional

from pkg.logger.logger import Logger
from internal.post_insight.interface import IPostInsightUseCase
from internal.builder.interface import IResultBuilderUseCase
from internal.text_preprocessing.interface import ITextPreprocessingUseCase
from internal.sentiment_analysis.interface import ISentimentAnalysisUseCase
from internal.intent_classification.interface import IIntentClassificationUseCase
from internal.keyword_extraction.interface import IKeywordExtractionUseCase
from internal.impact_calculation.interface import IImpactCalculationUseCase
from ..interface import IAnalyticsUseCase, IAnalyticsPublisher
from ..type import Config, Input, Output
from .process import AnalyticsProcess


class AnalyticsUseCase(IAnalyticsUseCase):
    def __init__(
        self,
        config: Config,
        post_insight_usecase: IPostInsightUseCase,
        logger: Optional[Logger] = None,
        *,
        preprocessor: Optional[ITextPreprocessingUseCase] = None,
        intent_classifier: Optional[IIntentClassificationUseCase] = None,
        keyword_extractor: Optional[IKeywordExtractionUseCase] = None,
        sentiment_analyzer: Optional[ISentimentAnalysisUseCase] = None,
        impact_calculator: Optional[IImpactCalculationUseCase] = None,
        result_builder: Optional[IResultBuilderUseCase] = None,
        analytics_publisher: Optional[IAnalyticsPublisher] = None,
    ):
        self.logger = logger
        self.process_logic = AnalyticsProcess(
            config=config,
            post_insight_usecase=post_insight_usecase,
            logger=self.logger,
            preprocessor=preprocessor,
            intent_classifier=intent_classifier,
            keyword_extractor=keyword_extractor,
            sentiment_analyzer=sentiment_analyzer,
            impact_calculator=impact_calculator,
            result_builder=result_builder,
            analytics_publisher=analytics_publisher,
        )

    async def process(self, input_data: Input) -> Output:
        return await self.process_logic.execute(input_data)
