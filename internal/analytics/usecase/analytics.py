from internal.consumer.type import Dependencies
from internal.analytics.interface import IAnalyticsUseCase
from internal.analytics.type import AnalyticsResult


class AnalyticsUseCase(IAnalyticsUseCase):
    """Use case for analytics processing.

    This class contains the core business logic:
    - Text extraction and validation
    - Sentiment analysis
    - Keyword extraction
    - Result storage and caching
    """

    def __init__(self, deps: Dependencies):
        """Initialize analytics use case.

        Args:
            deps: Service dependencies
        """
        self.deps = deps
        self.logger = deps.logger
        self.sentiment = deps.sentiment
        self.keyword_extractor = deps.keyword_extractor
        self.db = deps.db
        self.redis = deps.redis

    async def process_analytics(self, data: dict) -> AnalyticsResult:
        """Process analytics data.

        Args:
            data: Parsed message data

        Returns:
            AnalyticsResult with processing results
        """
        message_id = data.get("id", "unknown")

        try:
            # Extract text from message
            text = self._extract_text(data)

            if not text or not text.strip():
                self.logger.warn(f"[Analytics] Empty text in message {message_id}")
                return AnalyticsResult(
                    message_id=message_id,
                    sentiment="",
                    confidence=0.0,
                    keywords=[],
                    success=False,
                    error_message="Empty text content",
                )

            # Process sentiment analysis
            sentiment_result = self.sentiment.predict(text, return_probabilities=True)
            self.logger.info(
                f"[Analytics] [{message_id}] Sentiment: {sentiment_result.sentiment} "
                f"(confidence: {sentiment_result.confidence:.2f})"
            )

            # Process keyword extraction
            keyword_result = self.keyword_extractor.extract(text)
            keywords = []

            if keyword_result.success:
                keywords = [kw.keyword for kw in keyword_result.keywords[:5]]
                self.logger.info(
                    f"[Analytics] [{message_id}] Keywords: {', '.join(keywords)}"
                )
            else:
                self.logger.warn(
                    f"[Analytics] [{message_id}] Keyword extraction failed: "
                    f"{keyword_result.error_message}"
                )

            # TODO: Store results in database
            # await self._store_results(message_id, sentiment_result, keywords)

            # TODO: Cache results in Redis
            # await self._cache_results(message_id, sentiment_result, keywords)

            # TODO: Publish results to output queue
            # await self._publish_results(message_id, sentiment_result, keywords)

            return AnalyticsResult(
                message_id=message_id,
                sentiment=sentiment_result.sentiment,
                confidence=sentiment_result.confidence,
                keywords=keywords,
                success=True,
            )

        except Exception as e:
            self.logger.error(f"[Analytics] [{message_id}] Processing failed: {e}")
            return AnalyticsResult(
                message_id=message_id,
                sentiment="",
                confidence=0.0,
                keywords=[],
                success=False,
                error_message=str(e),
            )

    def _extract_text(self, data: dict) -> str:
        """Extract text content from message data.

        Args:
            data: Message data

        Returns:
            Extracted text content
        """
        return data.get("text") or data.get("content") or data.get("message", "")


__all__ = ["AnalyticsUseCase"]
