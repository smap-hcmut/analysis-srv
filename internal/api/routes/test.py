"""Test API endpoints for validating analytics pipeline integration.

This module provides test endpoints to verify that AI models are properly
initialized and can process JSON input matching the master-proposal.md format.
"""

from fastapi import APIRouter, Depends, HTTPException, status  # type: ignore
from pydantic import BaseModel, Field  # type: ignore
from typing import Dict, Any, List, Optional

from internal.api.dependencies import get_phobert, get_spacyyake
from infrastructure.ai import PhoBERTONNX, SpacyYakeExtractor
from core.logger import logger


router = APIRouter(prefix="/test", tags=["testing"])


class AnalyticsTestRequest(BaseModel):
    """Test request matching master-proposal.md JSON format.

    This model validates incoming JSON for analytics processing tests.
    """

    meta: Dict[str, Any] = Field(..., description="Post metadata (id, platform, lang, etc.)")
    content: Dict[str, Any] = Field(..., description="Post content (title, text, media, etc.)")
    interaction: Dict[str, Any] = Field(..., description="Engagement metrics")
    author: Dict[str, Any] = Field(..., description="Author information")
    comments: List[Dict[str, Any]] = Field(default_factory=list, description="Comments on the post")

    class Config:
        json_schema_extra = {
            "example": {
                "meta": {
                    "id": "post_123",
                    "platform": "facebook",
                    "lang": "vi",
                    "collected_at": "2025-01-15T10:30:00Z",
                },
                "content": {
                    "title": "Đánh giá sản phẩm",
                    "text": "Sản phẩm chất lượng cao, rất hài lòng!",
                    "media": [],
                },
                "interaction": {"likes": 42, "shares": 5, "comments_count": 3},
                "author": {"id": "user_456", "name": "John Doe"},
                "comments": [],
            }
        }


class KeywordsDebugInfo(BaseModel):
    """Debug information for keyword extraction."""

    status: str = Field(..., description="Status of keyword extraction")
    model_available: bool = Field(..., description="Whether SpaCy-YAKE model is available")
    keywords: Optional[List[Dict[str, Any]]] = Field(
        None, description="Extracted keywords (if processed)"
    )
    metadata: Optional[Dict[str, Any]] = Field(None, description="Extraction metadata")

    model_config = {"protected_namespaces": ()}


class SentimentDebugInfo(BaseModel):
    """Debug information for sentiment analysis."""

    status: str = Field(..., description="Status of sentiment analysis")
    model_available: bool = Field(..., description="Whether PhoBERT model is available")
    sentiment: Optional[Dict[str, Any]] = Field(None, description="Sentiment result (if processed)")

    model_config = {"protected_namespaces": ()}


class AnalyticsTestResponse(BaseModel):
    """Full analytics debug response.

    Returns detailed information about the analytics processing,
    including model availability and processing results.
    """

    post_id: str = Field(..., description="Post identifier from input")
    preprocessing: Dict[str, Any] = Field(..., description="Preprocessing status/info")
    keywords: KeywordsDebugInfo = Field(..., description="Keyword extraction debug info")
    sentiment: SentimentDebugInfo = Field(..., description="Sentiment analysis debug info")
    metadata: Dict[str, Any] = Field(..., description="Request metadata")


@router.post("/analytics", response_model=AnalyticsTestResponse)
async def test_analytics(
    request: AnalyticsTestRequest,
    phobert: Optional[PhoBERTONNX] = Depends(lambda req: get_phobert_optional(req)),
    spacyyake: Optional[SpacyYakeExtractor] = Depends(lambda req: get_spacyyake_optional(req)),
):
    """Test endpoint for analytics pipeline validation.

    This endpoint accepts JSON input matching the format specified in master-proposal.md
    and returns detailed debug information about the analytics processing.

    **Purpose:**
    - Validate JSON input format
    - Verify AI models are initialized and accessible
    - Test full analytics pipeline integration
    - Provide debugging output for development

    **Note:**
    - Full preprocessing implementation is not in scope for this proposal
    - This endpoint focuses on model availability and basic integration testing

    Args:
        request: Analytics test request with post data
        phobert: PhoBERT model instance (optional, via dependency injection)
        spacyyake: SpaCy-YAKE extractor instance (optional, via dependency injection)

    Returns:
        AnalyticsTestResponse: Full debug response with processing status

    Raises:
        HTTPException: If there's an error processing the request
    """
    try:
        logger.info(
            f"Test analytics request received for post_id: {request.meta.get('id', 'unknown')}"
        )

        # Extract post ID
        post_id = request.meta.get("id", "unknown")

        # Extract text content for processing
        title = request.content.get("title", "")
        text = request.content.get("text", "")
        combined_text = f"{title} {text}".strip()

        # Initialize response components
        keywords_info = KeywordsDebugInfo(status="not_initialized", model_available=False)

        sentiment_info = SentimentDebugInfo(status="not_initialized", model_available=False)

        # Process with SpaCy-YAKE if available
        if spacyyake is not None and combined_text:
            try:
                logger.info("Extracting keywords with SpaCy-YAKE...")
                extraction_result = spacyyake.extract(combined_text)

                keywords_info = KeywordsDebugInfo(
                    status="success" if extraction_result.success else "failed",
                    model_available=True,
                    keywords=extraction_result.keywords if extraction_result.success else None,
                    metadata=(
                        extraction_result.metadata
                        if extraction_result.success
                        else {"error": extraction_result.error_message}
                    ),
                )
                logger.info(
                    f"Keywords extracted: {len(extraction_result.keywords) if extraction_result.success else 0}"
                )
            except Exception as e:
                logger.error(f"Keyword extraction error: {e}")
                keywords_info = KeywordsDebugInfo(
                    status="error", model_available=True, metadata={"error": str(e)}
                )
        else:
            keywords_info = KeywordsDebugInfo(
                status="model_unavailable" if spacyyake is None else "no_text",
                model_available=spacyyake is not None,
            )

        # Process with PhoBERT if available
        if phobert is not None and combined_text:
            try:
                logger.info("Analyzing sentiment with PhoBERT...")
                sentiment_result = phobert.predict(combined_text, return_probabilities=True)

                sentiment_info = SentimentDebugInfo(
                    status="success", model_available=True, sentiment=sentiment_result
                )
                logger.info(f"Sentiment: {sentiment_result.get('sentiment', 'unknown')}")
            except Exception as e:
                logger.error(f"Sentiment analysis error: {e}")
                sentiment_info = SentimentDebugInfo(
                    status="error", model_available=True, sentiment={"error": str(e)}
                )
        else:
            sentiment_info = SentimentDebugInfo(
                status="model_unavailable" if phobert is None else "no_text",
                model_available=phobert is not None,
            )

        # Build response
        response = AnalyticsTestResponse(
            post_id=post_id,
            preprocessing={
                "status": "not_implemented",
                "message": "Text preprocessing will be implemented in a future proposal",
                "input_text_length": len(combined_text),
            },
            keywords=keywords_info,
            sentiment=sentiment_info,
            metadata={
                "platform": request.meta.get("platform"),
                "language": request.meta.get("lang"),
                "collected_at": request.meta.get("collected_at"),
                "models_initialized": {
                    "phobert": phobert is not None,
                    "spacyyake": spacyyake is not None,
                },
            },
        )

        logger.info(f"Test analytics response prepared for post_id: {post_id}")
        return response

    except Exception as e:
        logger.error(f"Error processing test analytics request: {e}")
        logger.exception("Test analytics error details:")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing analytics request: {str(e)}",
        )


def get_phobert_optional(request) -> Optional[PhoBERTONNX]:
    """Get PhoBERT model if available, return None if not.

    Unlike get_phobert(), this doesn't raise an exception if the model
    is unavailable, allowing the test endpoint to report status gracefully.
    """
    if hasattr(request.app.state, "phobert"):
        return request.app.state.phobert
    return None


def get_spacyyake_optional(request) -> Optional[SpacyYakeExtractor]:
    """Get SpaCy-YAKE extractor if available, return None if not.

    Unlike get_spacyyake(), this doesn't raise an exception if the model
    is unavailable, allowing the test endpoint to report status gracefully.
    """
    if hasattr(request.app.state, "spacyyake"):
        return request.app.state.spacyyake
    return None
