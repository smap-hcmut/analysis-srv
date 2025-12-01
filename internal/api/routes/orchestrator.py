"""Dev/Test API endpoint that runs the full AnalyticsOrchestrator pipeline.

This route accepts a full Atomic JSON post and delegates processing to
`AnalyticsOrchestrator`, bypassing MinIO and RabbitMQ. It is intended for
development and debugging only.
"""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Request, status  # type: ignore
from pydantic import BaseModel, Field  # type: ignore
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from core.config import settings
from core.logger import logger
from infrastructure.ai import PhoBERTONNX
from models.database import Base
from repositories.analytics_repository import AnalyticsRepository
from services.analytics.orchestrator import AnalyticsOrchestrator
from services.analytics.sentiment import SentimentAnalyzer


router = APIRouter(prefix="/dev", tags=["dev-orchestrator"])


class OrchestratorRequest(BaseModel):
    """Request model matching Atomic JSON post structure."""

    meta: Dict[str, Any] = Field(..., description="Post metadata (id, platform, etc.)")
    content: Dict[str, Any] = Field(..., description="Post content (text, transcription, etc.)")
    interaction: Dict[str, Any] = Field(..., description="Engagement metrics")
    author: Dict[str, Any] = Field(..., description="Author information")
    comments: list[Dict[str, Any]] = Field(
        default_factory=list, description="Optional comments associated with the post"
    )

    model_config = {"protected_namespaces": ()}


class OrchestratorResponse(BaseModel):
    """Response model exposing orchestrator output for debugging."""

    status: str = Field(..., description="Processing status")
    data: Dict[str, Any] = Field(..., description="Final analytics payload")

    model_config = {"protected_namespaces": ()}


def _get_session_factory() -> sessionmaker:
    engine = create_engine(settings.database_url_sync)
    Base.metadata.bind = engine
    return sessionmaker(bind=engine)


def get_db() -> Session:
    session_factory = _get_session_factory()
    db = session_factory()
    try:
        yield db
    finally:
        db.close()


def get_phobert(request: Request) -> PhoBERTONNX | None:
    """Get PhoBERT model from app.state (loaded once during lifespan).

    Returns None if model is not available, allowing graceful degradation.
    """
    if hasattr(request.app.state, "phobert") and request.app.state.phobert is not None:
        return request.app.state.phobert
    return None


@router.post("/process-post-direct", response_model=OrchestratorResponse)
async def dev_process_post_direct(
    request: OrchestratorRequest,
    db: Session = Depends(get_db),
    phobert: PhoBERTONNX | None = Depends(get_phobert),
):
    """Dev/Test endpoint: process a single post JSON via AnalyticsOrchestrator."""
    try:
        repo = AnalyticsRepository(db)

        sentiment_analyzer = None
        if phobert is not None:
            sentiment_analyzer = SentimentAnalyzer(phobert)

        orchestrator = AnalyticsOrchestrator(
            repository=repo,
            sentiment_analyzer=sentiment_analyzer,
        )

        post_data = request.model_dump()
        result = orchestrator.process_post(post_data)

        return OrchestratorResponse(status="SUCCESS", data=result)
    except Exception as exc:
        logger.error("Error in dev_process_post_direct: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing post: {exc}",
        ) from exc
