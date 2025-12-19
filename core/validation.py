"""Environment validation for API service startup."""

import sys
from typing import List, Tuple

from core.config import settings
from core.logger import logger


def validate_api_environment() -> Tuple[bool, List[str]]:
    """Validate environment configuration for API service.
    
    Returns:
        Tuple of (is_valid, error_messages)
    """
    errors = []
    
    # Validate required database settings
    if not settings.database_url:
        errors.append("DATABASE_URL is required")
    elif not settings.database_url.startswith(('postgresql+asyncpg://', 'postgresql://')):
        errors.append("DATABASE_URL must be a valid PostgreSQL URL")
    
    # Validate API settings
    if settings.api_port <= 0 or settings.api_port > 65535:
        errors.append(f"API_PORT must be between 1-65535, got {settings.api_port}")
    
    if settings.api_workers <= 0:
        errors.append(f"API_WORKERS must be positive, got {settings.api_workers}")
    
    # Validate database pool settings
    if settings.database_pool_size <= 0:
        errors.append(f"DATABASE_POOL_SIZE must be positive, got {settings.database_pool_size}")
    
    if settings.database_max_overflow < 0:
        errors.append(f"DATABASE_MAX_OVERFLOW must be non-negative, got {settings.database_max_overflow}")
    
    # Validate logging level
    valid_log_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
    if settings.log_level.upper() not in valid_log_levels:
        errors.append(f"LOG_LEVEL must be one of {valid_log_levels}, got {settings.log_level}")
    
    # Check if we're in debug mode and warn about production
    if settings.debug:
        logger.warning(
            "DEBUG mode is enabled. This should be disabled in production for security and performance."
        )
    
    # Warn about CORS settings in production
    if not settings.debug and "*" in settings.api_cors_origins:
        logger.warning(
            "CORS is set to allow all origins (*). This should be restricted in production."
        )
    
    return len(errors) == 0, errors


def validate_and_exit_on_error():
    """Validate environment and exit with error code if validation fails."""
    logger.info("Validating environment configuration...")
    
    is_valid, errors = validate_api_environment()
    
    if not is_valid:
        logger.error("Environment validation failed:")
        for error in errors:
            logger.error(f"  - {error}")
        
        logger.error("Please fix the configuration errors and restart the service.")
        sys.exit(1)
    
    logger.info("Environment validation passed ✓")


def log_configuration_summary():
    """Log a summary of the current configuration."""
    logger.info("=== API Service Configuration ===")
    logger.info(f"Service: {settings.service_name} v{settings.service_version}")
    logger.info(f"API Host: {settings.api_host}:{settings.api_port}")
    logger.info(f"API Workers: {settings.api_workers}")
    logger.info(f"Log Level: {settings.log_level}")
    logger.info(f"Debug Mode: {settings.debug}")
    logger.info(f"Database Pool: {settings.database_pool_size} + {settings.database_max_overflow} overflow")
    
    # Mask sensitive database URL
    masked_db_url = settings.database_url.split('@')[0] + "@***"
    logger.info(f"Database: {masked_db_url}")
    
    cors_origins = settings.api_cors_origins
    if isinstance(cors_origins, list) and len(cors_origins) > 3:
        cors_display = f"{len(cors_origins)} origins"
    else:
        cors_display = str(cors_origins)
    logger.info(f"CORS Origins: {cors_display}")
    logger.info("=== Configuration Summary Complete ===")


if __name__ == "__main__":
    """Test environment validation."""
    validate_and_exit_on_error()
    log_configuration_summary()
    print("✅ Environment validation passed!")