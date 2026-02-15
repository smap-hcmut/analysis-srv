"""Factory function for creating analytics pipeline."""

from typing import Optional

from pkg.logger.logger import Logger
from internal.text_preprocessing.interface import ITextProcessing
from internal.intent_classification.interface import IIntentClassification
from internal.keyword_extraction.interface import IKeywordExtraction
from internal.sentiment_analysis.interface import ISentimentAnalysis
from internal.impact_calculation.interface import IImpactCalculation
from internal.analyzed_post.interface import IAnalyzedPostUseCase

from ..type import Config
from .usecase import AnalyticsPipeline


def New(
    config: Config,
    analyzed_post_usecase: IAnalyzedPostUseCase,
    logger: Optional[Logger] = None,
    preprocessor: Optional[ITextProcessing] = None,
    intent_classifier: Optional[IIntentClassification] = None,
    keyword_extractor: Optional[IKeywordExtraction] = None,
    sentiment_analyzer: Optional[ISentimentAnalysis] = None,
    impact_calculator: Optional[IImpactCalculation] = None,
) -> AnalyticsPipeline:
    """Create a new analytics pipeline instance.
    
    Args:
        config: Pipeline configuration
        analyzed_post_usecase: Use case for persisting analyzed posts
        logger: Logger instance (optional)
        preprocessor: Text preprocessor (optional)
        intent_classifier: Intent classifier (optional)
        keyword_extractor: Keyword extractor (optional)
        sentiment_analyzer: Sentiment analyzer (optional)
        impact_calculator: Impact calculator (optional)
        
    Returns:
        AnalyticsPipeline instance
        
    Raises:
        ValueError: If config is invalid
    """
    if not isinstance(config, Config):
        raise ValueError("config must be an instance of Config")
    
    return AnalyticsPipeline(
        config=config,
        analyzed_post_usecase=analyzed_post_usecase,
        logger=logger,
        preprocessor=preprocessor,
        intent_classifier=intent_classifier,
        keyword_extractor=keyword_extractor,
        sentiment_analyzer=sentiment_analyzer,
        impact_calculator=impact_calculator,
    )


__all__ = ["New"]
