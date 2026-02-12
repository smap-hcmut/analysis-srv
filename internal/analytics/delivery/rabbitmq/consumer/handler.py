"""Analytics message handler for RabbitMQ consumer.

This handler receives data.collected events from RabbitMQ and delegates
processing to the analytics orchestrator usecase.
"""

from __future__ import annotations

import json
import time
from typing import Any, Optional, TYPE_CHECKING

try:
    from aio_pika import IncomingMessage  # type: ignore

    AIO_PIKA_AVAILABLE = True
except ImportError:
    AIO_PIKA_AVAILABLE = False
    if TYPE_CHECKING:
        from aio_pika import IncomingMessage  # type: ignore
    else:
        IncomingMessage = Any

from pkg.logger.logger import Logger
from internal.analytics.interface import IAnalyticsPipeline
from internal.analytics.type import Input, PostData


class AnalyticsHandler:
    """Handler for processing analytics messages from RabbitMQ.

    This class acts as an adapter between the message queue and the
    analytics pipeline usecase. It:
    1. Receives and validates incoming messages
    2. Parses event payload
    3. Delegates to analytics orchestrator
    4. Handles errors and logging
    """

    def __init__(
        self,
        pipeline: IAnalyticsPipeline,
        logger: Optional[Logger] = None,
    ):
        """Initialize analytics handler.

        Args:
            pipeline: Analytics pipeline instance
            logger: Logger instance (optional)
        """
        self.pipeline = pipeline
        self.logger = logger

    async def handle(self, message: IncomingMessage) -> None:
        """Handle incoming message (called by consumer server).
        
        Args:
            message: Incoming message from RabbitMQ
        """
        await self.handle_message(message)

    async def handle_message(self, message: IncomingMessage) -> None:
        """Handle incoming data.collected event from RabbitMQ.

        Args:
            message: Incoming message from RabbitMQ

        Raises:
            Exception: If message processing fails (will trigger nack)
        """
        async with message.process():
            start_time = time.perf_counter()
            event_id = "unknown"

            try:
                body = message.body.decode("utf-8")
                envelope = json.loads(body)
                event_id = envelope.get("event_id", "unknown")

                if self.logger:
                    self.logger.debug(
                        f"[AnalyticsHandler] Received message: event_id={event_id}"
                    )

                if not self._validate_event(envelope):
                    raise ValueError("Invalid event format: missing required fields")

                event_metadata = self._parse_event_metadata(envelope)
                post_data = self._extract_post_data(envelope)
                project_id = self._extract_project_id(event_metadata)

                pipeline_input = Input(
                    post_data=post_data,
                    event_metadata=event_metadata,
                    project_id=project_id,
                )

                output = await self.pipeline.process(pipeline_input)
                elapsed_ms = int((time.perf_counter() - start_time) * 1000)

                if self.logger:
                    self.logger.info(
                        f"[AnalyticsHandler] Message processed: event_id={event_id}, "
                        f"status={output.processing_status}, elapsed_ms={elapsed_ms}"
                    )

            except json.JSONDecodeError as exc:
                if self.logger:
                    self.logger.error(
                        f"[AnalyticsHandler] Invalid JSON: event_id={event_id}, error={exc}"
                    )
                raise

            except ValueError as exc:
                if self.logger:
                    self.logger.error(
                        f"[AnalyticsHandler] Validation error: event_id={event_id}, error={exc}"
                    )
                raise

            except Exception as exc:
                if self.logger:
                    self.logger.error(
                        f"[AnalyticsHandler] Processing error: event_id={event_id}, error={exc}"
                    )
                raise

    def _validate_event(self, envelope: dict[str, Any]) -> bool:
        """Validate event format.

        Args:
            envelope: Parsed JSON message envelope

        Returns:
            True if valid, False otherwise
        """
        if "payload" not in envelope:
            return False

        payload = envelope.get("payload", {})

        # Check for required fields
        # Either minio_path (batch) or inline post data
        has_minio_path = "minio_path" in payload
        has_inline_data = "meta" in payload

        return has_minio_path or has_inline_data

    def _parse_event_metadata(self, envelope: dict[str, Any]) -> dict[str, Any]:
        """Extract metadata from event envelope.

        Args:
            envelope: Event envelope

        Returns:
            Dictionary with event metadata
        """
        payload = envelope.get("payload", {})

        return {
            "event_id": envelope.get("event_id"),
            "event_type": envelope.get("event_type"),
            "timestamp": envelope.get("timestamp"),
            "minio_path": payload.get("minio_path"),
            "project_id": payload.get("project_id"),
            "job_id": payload.get("job_id"),
            "batch_index": payload.get("batch_index"),
            "content_count": payload.get("content_count"),
            "platform": payload.get("platform"),
            "task_type": payload.get("task_type"),
            "brand_name": payload.get("brand_name"),
            "keyword": payload.get("keyword"),
        }

    def _extract_post_data(self, envelope: dict[str, Any]) -> PostData:
        """Extract post data from envelope.

        For now, assumes inline data. MinIO batch processing will be
        handled separately.

        Args:
            envelope: Event envelope

        Returns:
            PostData instance
        """
        payload = envelope.get("payload", {})

        # For inline data
        return PostData(
            meta=payload.get("meta", {}),
            content=payload.get("content", {}),
            interaction=payload.get("interaction", {}),
            author=payload.get("author", {}),
            comments=payload.get("comments", []),
        )

    def _extract_project_id(self, event_metadata: dict[str, Any]) -> Optional[str]:
        """Extract project_id from event metadata.

        Args:
            event_metadata: Event metadata dictionary

        Returns:
            Project ID or None
        """
        # Try direct project_id first
        project_id = event_metadata.get("project_id")
        if project_id:
            return project_id

        # Try extracting from job_id (format: "uuid-suffix")
        job_id = event_metadata.get("job_id", "")
        if "-" in job_id:
            parts = job_id.split("-", 1)
            if len(parts[0]) == 36:  # UUID length
                return parts[0]

        return None


__all__ = ["AnalyticsHandler"]
