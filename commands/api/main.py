"""
Analytics Engine API - Main entry point.
Loads config, initializes instances, and starts the FastAPI service.
"""

import warnings
from contextlib import asynccontextmanager

# Suppress expected warnings at startup
warnings.filterwarnings("ignore", message=".*protected namespace.*", category=UserWarning)

from fastapi import FastAPI, Request, HTTPException, status as http_status  # type: ignore
from fastapi.middleware.cors import CORSMiddleware  # type: ignore
from fastapi.responses import JSONResponse  # type: ignore
from fastapi.exceptions import RequestValidationError  # type: ignore

from core.config import settings
from core.logger import logger
from internal.api.main import app as internal_app


# Lifespan context manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manage application lifespan - startup and shutdown.
    Initialize AI models once and reuse across requests.
    """
    try:
        logger.info(
            f"========== Starting {settings.service_name} v{settings.service_version} API service =========="
        )
        logger.info(f"API: {settings.api_host}:{settings.api_port}")

        # Initialize AI models
        logger.info("Loading AI models...")

        from infrastructure.ai import PhoBERTONNX, SpacyYakeExtractor

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

        # Initialize SpaCy-YAKE
        try:
            logger.info("Initializing SpaCy-YAKE extractor...")
            app.state.spacyyake = SpacyYakeExtractor(
                spacy_model=settings.spacy_model,
                yake_language=settings.yake_language,
                yake_n=settings.yake_n,
                yake_dedup_lim=settings.yake_dedup_lim,
                yake_max_keywords=settings.yake_max_keywords,
                max_keywords=settings.max_keywords,
                entity_weight=settings.entity_weight,
                chunk_weight=settings.chunk_weight,
            )
            logger.info("SpaCy-YAKE extractor loaded successfully")
        except Exception as e:
            logger.error(f"Failed to initialize SpaCy-YAKE: {e}")
            logger.exception("SpaCy-YAKE initialization error details:")
            app.state.spacyyake = None

        # Log final status
        models_loaded = []
        if app.state.phobert:
            models_loaded.append("PhoBERT")
        if app.state.spacyyake:
            models_loaded.append("SpaCy-YAKE")

        if models_loaded:
            logger.info(f"AI models loaded successfully: {', '.join(models_loaded)}")
        else:
            logger.warning("API starting without AI models - test endpoint will report unavailable")

        logger.info(
            f"========== {settings.service_name} API service started successfully =========="
        )

        yield

        # Shutdown sequence
        logger.info("========== Shutting down API service ==========")

        # Cleanup AI models
        logger.info("Cleaning up AI models...")
        if hasattr(app.state, "phobert") and app.state.phobert is not None:
            del app.state.phobert
            logger.info("PhoBERT model cleaned up")
        if hasattr(app.state, "spacyyake") and app.state.spacyyake is not None:
            del app.state.spacyyake
            logger.info("SpaCy-YAKE extractor cleaned up")

        logger.info("========== API service stopped successfully ==========")

    except Exception as e:
        logger.error(f"Fatal error in application lifespan: {e}")
        logger.exception("Lifespan error details:")
        raise


def create_app() -> FastAPI:
    """
    Factory function to create and configure the FastAPI application.

    Returns:
        FastAPI: Configured application instance
    """
    try:
        logger.info("Creating FastAPI application...")

        # Use the app from internal/api/main.py and add lifespan
        app = internal_app
        app.router.lifespan_context = lifespan

        logger.info("FastAPI application created successfully")
        return app

    except Exception as e:
        logger.error(f"Failed to create FastAPI application: {e}")
        logger.exception("Application creation error details:")
        raise


# Create application instance
try:
    logger.info("Initializing Analytics Engine API...")
    app = create_app()
    logger.info("Application instance created successfully")
except Exception as e:
    logger.error(f"Failed to create application instance: {e}")
    logger.exception("Startup error details:")
    raise


# Run with: uv run commands/api/main.py
if __name__ == "__main__":
    import uvicorn  # type: ignore
    import sys
    import os

    try:
        logger.info("========== Starting Uvicorn Server ==========")
        logger.info(f"Host: {settings.api_host}")
        logger.info(f"Port: {settings.api_port}")
        logger.info(f"Reload: {settings.api_reload}")

        # Ensure project root is in PYTHONPATH
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        if project_root not in sys.path:
            sys.path.insert(0, project_root)

        # Set PYTHONPATH environment variable for subprocess (uvicorn reload)
        current_pythonpath = os.environ.get("PYTHONPATH", "")
        if project_root not in current_pythonpath:
            new_pythonpath = (
                f"{project_root}:{current_pythonpath}" if current_pythonpath else project_root
            )
            os.environ["PYTHONPATH"] = new_pythonpath

        # Use string path when reload=True
        if settings.api_reload:
            uvicorn.run(
                "commands.api.main:app",
                host=settings.api_host,
                port=settings.api_port,
                reload=True,
                log_level="info",
            )
        else:
            uvicorn.run(
                app,
                host=settings.api_host,
                port=settings.api_port,
                reload=False,
                log_level="info",
            )

    except Exception as e:
        logger.error(f"Failed to start Uvicorn server: {e}")
        logger.exception("Uvicorn startup error details:")
        raise
