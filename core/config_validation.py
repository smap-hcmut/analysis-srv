"""Configuration validation for Analytics Engine.

This module provides startup validation for critical configuration settings
to ensure the service can operate correctly before processing any messages.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import List, Optional
from urllib.parse import urlparse

from core.config import settings
from core.logger import logger


@dataclass
class ValidationResult:
    """Result of a configuration validation check."""

    name: str
    valid: bool
    message: str
    severity: str = "error"  # error, warning, info


class ConfigValidator:
    """Validates configuration settings on startup."""

    def __init__(self) -> None:
        self._results: List[ValidationResult] = []

    def validate_all(self) -> bool:
        """Run all validation checks.

        Returns:
            True if all critical validations pass, False otherwise.
        """
        self._results = []

        # Database validations
        self._validate_database_url()

        # RabbitMQ validations
        self._validate_rabbitmq_url()

        # MinIO validations
        self._validate_minio_settings()

        # Batch processing validations
        self._validate_batch_settings()

        # Event queue validations
        self._validate_event_queue_settings()

        # Log results
        self._log_results()

        # Return True if no errors
        errors = [r for r in self._results if not r.valid and r.severity == "error"]
        return len(errors) == 0

    def _validate_database_url(self) -> None:
        """Validate database connection URL."""
        # Check sync URL
        if not settings.database_url_sync:
            self._results.append(
                ValidationResult(
                    name="database_url_sync",
                    valid=False,
                    message="DATABASE_URL_SYNC is not configured",
                )
            )
            return

        try:
            parsed = urlparse(settings.database_url_sync)
            if parsed.scheme not in ("postgresql", "postgres"):
                self._results.append(
                    ValidationResult(
                        name="database_url_sync",
                        valid=False,
                        message=f"Invalid database scheme: {parsed.scheme}. Expected postgresql",
                    )
                )
            elif not parsed.hostname:
                self._results.append(
                    ValidationResult(
                        name="database_url_sync",
                        valid=False,
                        message="Database URL missing hostname",
                    )
                )
            else:
                self._results.append(
                    ValidationResult(
                        name="database_url_sync",
                        valid=True,
                        message=f"Database configured: {parsed.hostname}:{parsed.port or 5432}",
                    )
                )
        except Exception as e:
            self._results.append(
                ValidationResult(
                    name="database_url_sync",
                    valid=False,
                    message=f"Invalid database URL: {e}",
                )
            )

    def _validate_rabbitmq_url(self) -> None:
        """Validate RabbitMQ connection URL."""
        if not settings.rabbitmq_url:
            self._results.append(
                ValidationResult(
                    name="rabbitmq_url",
                    valid=False,
                    message="RABBITMQ_URL is not configured",
                )
            )
            return

        try:
            parsed = urlparse(settings.rabbitmq_url)
            if parsed.scheme not in ("amqp", "amqps"):
                self._results.append(
                    ValidationResult(
                        name="rabbitmq_url",
                        valid=False,
                        message=f"Invalid RabbitMQ scheme: {parsed.scheme}. Expected amqp/amqps",
                    )
                )
            elif not parsed.hostname:
                self._results.append(
                    ValidationResult(
                        name="rabbitmq_url",
                        valid=False,
                        message="RabbitMQ URL missing hostname",
                    )
                )
            else:
                self._results.append(
                    ValidationResult(
                        name="rabbitmq_url",
                        valid=True,
                        message=f"RabbitMQ configured: {parsed.hostname}:{parsed.port or 5672}",
                    )
                )
        except Exception as e:
            self._results.append(
                ValidationResult(
                    name="rabbitmq_url",
                    valid=False,
                    message=f"Invalid RabbitMQ URL: {e}",
                )
            )

    def _validate_minio_settings(self) -> None:
        """Validate MinIO configuration."""
        # Endpoint
        if not settings.minio_endpoint:
            self._results.append(
                ValidationResult(
                    name="minio_endpoint",
                    valid=False,
                    message="MINIO_ENDPOINT is not configured",
                )
            )
        else:
            try:
                parsed = urlparse(settings.minio_endpoint)
                if parsed.scheme not in ("http", "https"):
                    self._results.append(
                        ValidationResult(
                            name="minio_endpoint",
                            valid=False,
                            message=f"Invalid MinIO scheme: {parsed.scheme}",
                        )
                    )
                else:
                    self._results.append(
                        ValidationResult(
                            name="minio_endpoint",
                            valid=True,
                            message=f"MinIO endpoint: {settings.minio_endpoint}",
                        )
                    )
            except Exception as e:
                self._results.append(
                    ValidationResult(
                        name="minio_endpoint",
                        valid=False,
                        message=f"Invalid MinIO endpoint: {e}",
                    )
                )

        # Credentials
        if not settings.minio_access_key or not settings.minio_secret_key:
            self._results.append(
                ValidationResult(
                    name="minio_credentials",
                    valid=False,
                    message="MinIO credentials not configured",
                )
            )
        else:
            self._results.append(
                ValidationResult(
                    name="minio_credentials",
                    valid=True,
                    message="MinIO credentials configured",
                )
            )

        # Bucket
        if not settings.minio_crawl_results_bucket:
            self._results.append(
                ValidationResult(
                    name="minio_bucket",
                    valid=False,
                    message="MINIO_CRAWL_RESULTS_BUCKET is not configured",
                    severity="warning",
                )
            )
        else:
            self._results.append(
                ValidationResult(
                    name="minio_bucket",
                    valid=True,
                    message=f"Crawl results bucket: {settings.minio_crawl_results_bucket}",
                )
            )

    def _validate_batch_settings(self) -> None:
        """Validate batch processing settings."""
        # Batch sizes
        if settings.expected_batch_size_tiktok <= 0:
            self._results.append(
                ValidationResult(
                    name="batch_size_tiktok",
                    valid=False,
                    message="EXPECTED_BATCH_SIZE_TIKTOK must be positive",
                    severity="warning",
                )
            )

        if settings.expected_batch_size_youtube <= 0:
            self._results.append(
                ValidationResult(
                    name="batch_size_youtube",
                    valid=False,
                    message="EXPECTED_BATCH_SIZE_YOUTUBE must be positive",
                    severity="warning",
                )
            )

        # Timeout
        if settings.batch_timeout_seconds <= 0:
            self._results.append(
                ValidationResult(
                    name="batch_timeout",
                    valid=False,
                    message="BATCH_TIMEOUT_SECONDS must be positive",
                    severity="warning",
                )
            )
        elif settings.batch_timeout_seconds < 10:
            self._results.append(
                ValidationResult(
                    name="batch_timeout",
                    valid=True,
                    message=f"Batch timeout is low ({settings.batch_timeout_seconds}s), may cause issues with large batches",
                    severity="warning",
                )
            )
        else:
            self._results.append(
                ValidationResult(
                    name="batch_timeout",
                    valid=True,
                    message=f"Batch timeout: {settings.batch_timeout_seconds}s",
                )
            )

        # Concurrent batches
        if settings.max_concurrent_batches <= 0:
            self._results.append(
                ValidationResult(
                    name="max_concurrent_batches",
                    valid=False,
                    message="MAX_CONCURRENT_BATCHES must be positive",
                    severity="warning",
                )
            )
        elif settings.max_concurrent_batches > 20:
            self._results.append(
                ValidationResult(
                    name="max_concurrent_batches",
                    valid=True,
                    message=f"High concurrent batches ({settings.max_concurrent_batches}), ensure sufficient resources",
                    severity="warning",
                )
            )

    def _validate_event_queue_settings(self) -> None:
        """Validate event queue configuration."""
        # Validate event exchange
        if not settings.event_exchange:
            self._results.append(
                ValidationResult(
                    name="event_exchange",
                    valid=False,
                    message="EVENT_EXCHANGE is not configured",
                )
            )
        else:
            self._results.append(
                ValidationResult(
                    name="event_exchange",
                    valid=True,
                    message=f"Event exchange: {settings.event_exchange}",
                    severity="info",
                )
            )

        # Validate event queue name
        if not settings.event_queue_name:
            self._results.append(
                ValidationResult(
                    name="event_queue_name",
                    valid=False,
                    message="EVENT_QUEUE_NAME is not configured",
                )
            )
        else:
            self._results.append(
                ValidationResult(
                    name="event_queue_name",
                    valid=True,
                    message=f"Event queue: {settings.event_queue_name}",
                    severity="info",
                )
            )

    def _log_results(self) -> None:
        """Log validation results."""
        errors = [r for r in self._results if not r.valid and r.severity == "error"]
        warnings = [r for r in self._results if not r.valid and r.severity == "warning"]

        logger.info("=" * 60)
        logger.info("Configuration Validation Results")
        logger.info("=" * 60)

        for result in self._results:
            if result.valid:
                if result.severity == "warning":
                    logger.warning(f"[WARN] {result.name}: {result.message}")
                else:
                    logger.info(f"[OK] {result.name}: {result.message}")
            else:
                if result.severity == "error":
                    logger.error(f"[FAIL] {result.name}: {result.message}")
                else:
                    logger.warning(f"[WARN] {result.name}: {result.message}")

        logger.info("=" * 60)
        if errors:
            logger.error(f"Validation FAILED: {len(errors)} error(s), {len(warnings)} warning(s)")
        elif warnings:
            logger.warning(f"Validation PASSED with {len(warnings)} warning(s)")
        else:
            logger.info("Validation PASSED: All checks OK")
        logger.info("=" * 60)

    def get_results(self) -> List[ValidationResult]:
        """Get all validation results."""
        return self._results.copy()


def validate_config_on_startup() -> bool:
    """Validate configuration on service startup.

    Returns:
        True if validation passes, False otherwise.
    """
    validator = ConfigValidator()
    return validator.validate_all()
