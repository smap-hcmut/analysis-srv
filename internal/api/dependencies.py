"""Dependency injection for API endpoints.

Provides FastAPI dependencies for accessing AI model instances
that are initialized once during application startup.
"""

from fastapi import Depends, Request, HTTPException, status # type: ignore
from infrastructure.ai import PhoBERTONNX, SpacyYakeExtractor


def get_phobert(request: Request) -> PhoBERTONNX:
    """Dependency injection for PhoBERT model.

    Args:
        request: FastAPI request object containing app state

    Returns:
        PhoBERTONNX: Initialized PhoBERT model instance

    Raises:
        HTTPException: If PhoBERT model is not initialized (503 Service Unavailable)

    Example:
        ```python
        @router.post("/analyze")
        async def analyze(
            text: str,
            phobert: PhoBERTONNX = Depends(get_phobert)
        ):
            result = phobert.predict(text)
            return result
        ```
    """
    if not hasattr(request.app.state, "phobert") or request.app.state.phobert is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="PhoBERT model is not available. The service may still be starting up or failed to initialize."
        )
    return request.app.state.phobert


def get_spacyyake(request: Request) -> SpacyYakeExtractor:
    """Dependency injection for SpaCy-YAKE extractor.

    Args:
        request: FastAPI request object containing app state

    Returns:
        SpacyYakeExtractor: Initialized SpaCy-YAKE extractor instance

    Raises:
        HTTPException: If SpaCy-YAKE extractor is not initialized (503 Service Unavailable)

    Example:
        ```python
        @router.post("/extract")
        async def extract(
            text: str,
            spacyyake: SpacyYakeExtractor = Depends(get_spacyyake)
        ):
            result = spacyyake.extract(text)
            return result
        ```
    """
    if not hasattr(request.app.state, "spacyyake") or request.app.state.spacyyake is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="SpaCy-YAKE extractor is not available. The service may still be starting up or failed to initialize."
        )
    return request.app.state.spacyyake
