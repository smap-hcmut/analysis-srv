"""FastAPI application entry point for Analytics Engine."""

from contextlib import asynccontextmanager

from fastapi import FastAPI  # type: ignore
from fastapi.middleware.cors import CORSMiddleware  # type: ignore
from fastapi.responses import RedirectResponse  # type: ignore

from core.config import settings
from core.logger import logger
from internal.api.routes import test, orchestrator


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manage application lifespan - startup and shutdown.
    Initialize AI models once and reuse across requests.
    """
    try:
        logger.info("Initializing Analytics Engine API...")

        # Initialize AI models
        logger.info("Loading AI models...")

        from infrastructure.ai import PhoBERTONNX

        # Initialize PhoBERT
        try:
            logger.info("Initializing PhoBERT ONNX model...")
            app.state.phobert = PhoBERTONNX(
                model_path=settings.phobert_model_path, max_length=settings.phobert_max_length
            )
            logger.info("PhoBERT ONNX model loaded successfully")
        except Exception as e:
            logger.error(f"Failed to initialize PhoBERT: {e}")
            logger.exception("PhoBERT initialization error details:")
            app.state.phobert = None

        # Log final status
        if app.state.phobert:
            logger.info("AI models loaded successfully: PhoBERT")
        else:
            logger.warning("API starting without PhoBERT model - dev endpoint will use fallback")

        logger.info("Analytics Engine API started successfully")

        yield

        # Shutdown sequence
        logger.info("Shutting down API service...")

        # Cleanup AI models
        if hasattr(app.state, "phobert") and app.state.phobert is not None:
            del app.state.phobert
            logger.info("PhoBERT model cleaned up")

        logger.info("API service stopped successfully")

    except Exception as e:
        logger.error(f"Fatal error in application lifespan: {e}")
        logger.exception("Lifespan error details:")
        raise


app = FastAPI(
    title="Analytics Engine API",
    description="Social media analytics processing service",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/swagger",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(test.router)
app.include_router(orchestrator.router)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "analytics-engine"}


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "Analytics Engine API",
        "version": "0.1.0",
        "status": "running",
    }


@app.get("/swagger/index.html", include_in_schema=False)
async def swagger_redirect():
    """Redirect /swagger/index.html to /swagger for Swagger UI access."""
    return RedirectResponse(url="/swagger")


if __name__ == "__main__":
    import uvicorn  # type: ignore

    uvicorn.run(
        "internal.api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
