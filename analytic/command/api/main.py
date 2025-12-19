"""
Analytics Engine API Service - Main entry point.
Loads config, initializes FastAPI app, starts the API server.
Serves analytics data via REST API endpoints.
"""

import uvicorn
from core.config import settings
from core.logger import logger
from core.validation import validate_and_exit_on_error, log_configuration_summary
from internal.api.main import app


def main():
    """Entry point for the Analytics Engine API service."""
    try:
        logger.info(
            f"========== Starting {settings.service_name} v{settings.service_version} API service =========="
        )
        
        # Validate environment configuration
        validate_and_exit_on_error()
        
        # Log configuration summary
        log_configuration_summary()
        
        # Start API server with Uvicorn
        logger.info("Starting API server...")
        uvicorn.run(
            app=app,
            host=settings.api_host,
            port=settings.api_port,
            log_level=settings.log_level.lower(),
            access_log=True,
            workers=settings.api_workers if hasattr(settings, 'api_workers') else 1,
            root_path=settings.api_root_path if settings.api_root_path else None,  # Handle ingress prefix
        )
        
    except KeyboardInterrupt:
        logger.info("API service stopped by user")
    except Exception as e:
        logger.error(f"API service error: {e}")
        logger.exception("API service error details:")
        raise
    finally:
        logger.info("========== API service stopped ==========")


if __name__ == "__main__":
    main()