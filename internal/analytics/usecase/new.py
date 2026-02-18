from typing import Optional

from pkg.logger.logger import Logger
from internal.text_preprocessing.interface import ITextPreprocessingUseCase
from internal.intent_classification.interface import IIntentClassificationUseCase
from internal.keyword_extraction.interface import IKeywordExtractionUseCase
from internal.sentiment_analysis.interface import ISentimentAnalysisUseCase
from internal.impact_calculation.interface import IImpactCalculationUseCase
from internal.post_insight.interface import IPostInsightUseCase
from internal.builder.interface import IResultBuilderUseCase
from internal.analytics.interface import IAnalyticsPublisher

from ..interface import IAnalyticsUseCase, IAnalyticsPublisher
from ..type import Config
from .usecase import AnalyticsUseCase


def New(
    config: Config,
    post_insight_usecase: IPostInsightUseCase,
    logger: Optional[Logger] = None,
    preprocessor: Optional[ITextPreprocessingUseCase] = None,
    intent_classifier: Optional[IIntentClassificationUseCase] = None,
    keyword_extractor: Optional[IKeywordExtractionUseCase] = None,
    sentiment_analyzer: Optional[ISentimentAnalysisUseCase] = None,
    impact_calculator: Optional[IImpactCalculationUseCase] = None,
    result_builder: Optional[IResultBuilderUseCase] = None,
    analytics_publisher: Optional[IAnalyticsPublisher] = None,
) -> IAnalyticsUseCase: 
    return AnalyticsUseCase(
        config=config,
        post_insight_usecase=post_insight_usecase,
        logger=logger,
        preprocessor=preprocessor,
        intent_classifier=intent_classifier,
        keyword_extractor=keyword_extractor,
        sentiment_analyzer=sentiment_analyzer,
        impact_calculator=impact_calculator,
        result_builder=result_builder,
        analytics_publisher=analytics_publisher,
    )


__all__ = ["New"]
