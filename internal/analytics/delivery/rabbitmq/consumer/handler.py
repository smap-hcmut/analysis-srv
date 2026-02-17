"""Analytics message handler for RabbitMQ consumer.

Convention: Delivery handler is THIN.
1. Receive message
2. Parse into delivery DTOs (presenters)
3. Validate format (structural only)
4. Convert to usecase Input (presenters.to_pipeline_input)
5. Call usecase
6. Log / ACK or NACK
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
from internal.analytics.delivery.constant import FIELD_PAYLOAD, FIELD_META, FIELD_MINIO_PATH
from .presenters import (
    parse_message,
    parse_event_metadata,
    parse_post_payload,
    to_pipeline_input,
)


class AnalyticsHandler:
    """Handler for processing analytics messages from RabbitMQ.

    This class acts as an adapter between the message queue and the
    analytics pipeline usecase. NO business logic here.
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
        """Handle incoming message (called by consumer server)."""
        await self.handle_message(message)

    async def handle_message(self, message: IncomingMessage) -> None:
        """Handle incoming data.collected event from RabbitMQ.

        Flow: Receive → Parse (presenters) → Validate → Convert (to_input) → UseCase → Log
        """
        async with message.process():
            start_time = time.perf_counter()
            event_id = "unknown"

            try:
                # 1. Parse message body
                body = message.body.decode("utf-8")
                envelope = json.loads(body)

                # 2. Parse into delivery DTOs
                msg_dto = parse_message(envelope)
                event_id = msg_dto.event_id or "unknown"

                if self.logger:
                    self.logger.debug(
                        f"[AnalyticsHandler] Received message: event_id={event_id}"
                    )

                # 3. Validate format (structural only — no business logic)
                if not self._validate_format(envelope):
                    raise ValueError("Invalid event format: missing required fields")

                # 4. Convert delivery DTOs → domain Input
                post_dto = parse_post_payload(msg_dto)
                meta_dto = parse_event_metadata(msg_dto)
                pipeline_input = to_pipeline_input(msg_dto, post_dto, meta_dto)

                # 5. Call UseCase
                output = await self.pipeline.process(pipeline_input)

                # 6. Log result
                elapsed_ms = int((time.perf_counter() - start_time) * 1000)
                if self.logger:
                    self.logger.info(
                        f"[AnalyticsHandler] Message processed: event_id={event_id}, "
                        f"status={output.processing_status}, elapsed_ms={elapsed_ms}"
                    )

            except json.JSONDecodeError as exc:
                # Poison message — ACK (discard)
                if self.logger:
                    self.logger.error(
                        f"[AnalyticsHandler] Invalid JSON: event_id={event_id}, error={exc}"
                    )
                raise

            except ValueError as exc:
                # Structural validation error — ACK (discard)
                if self.logger:
                    self.logger.error(
                        f"[AnalyticsHandler] Validation error: event_id={event_id}, error={exc}"
                    )
                raise

            except Exception as exc:
                # Business/transient error — NACK (retry)
                if self.logger:
                    self.logger.error(
                        f"[AnalyticsHandler] Processing error: event_id={event_id}, error={exc}"
                    )
                raise

    def _validate_format(self, envelope: dict[str, Any]) -> bool:
        """Validate event format (structural only).

        Convention: Only structural validation here.
        Business validation belongs in UseCase.
        """
        if FIELD_PAYLOAD not in envelope:
            return False

        payload = envelope.get(FIELD_PAYLOAD, {})
        has_minio_path = FIELD_MINIO_PATH in payload
        has_inline_data = FIELD_META in payload

        return has_minio_path or has_inline_data


__all__ = ["AnalyticsHandler"]
