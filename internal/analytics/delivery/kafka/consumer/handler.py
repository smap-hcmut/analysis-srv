from __future__ import annotations

import json
import time
from typing import Optional

from pkg.logger.logger import Logger
from pkg.kafka.type import KafkaMessage
from internal.analytics.interface import IAnalyticsUseCase
from internal.analytics.delivery.constant import FIELD_UAP_VERSION
from internal.model.uap import UAPRecord, ErrUAPValidation, ErrUAPVersionUnsupported
from internal.analytics.delivery.presenters import to_pipeline_input


class AnalyticsKafkaHandler:
    def __init__(
        self,
        pipeline: IAnalyticsUseCase,
        logger: Optional[Logger] = None,
    ):
        self.pipeline = pipeline
        self.logger = logger

    async def handle(self, message: KafkaMessage) -> None:
        start_time = time.perf_counter()
        event_id = "unknown"

        try:
            # 1. Parse message value (JSON)
            if isinstance(message.value, bytes):
                body = message.value.decode("utf-8")
            elif isinstance(message.value, str):
                body = message.value
            else:
                body = json.dumps(message.value)

            envelope = json.loads(body)

            # 2. Check UAP Version
            if FIELD_UAP_VERSION not in envelope:
                # Reject legacy messages
                if self.logger:
                    self.logger.warning(
                        f"internal.analytics.delivery.kafka.consumer.handler: Missing {FIELD_UAP_VERSION}: legacy format not supported, "
                        f"topic={message.topic}, partition={message.partition}, offset={message.offset}"
                    )
                # Skip this message (will commit offset)
                return

            # 3. Parse UAP and Convert
            pipeline_input = self._handle_uap(envelope)

            # Extract event_id for logging
            if pipeline_input.uap_record and pipeline_input.uap_record.event_id:
                event_id = pipeline_input.uap_record.event_id
            else:
                event_id = envelope.get("event_id", "unknown")

            if self.logger:
                self.logger.debug(
                    f"internal.analytics.delivery.kafka.consumer.handler: Received message: event_id={event_id}, "
                    f"topic={message.topic}, partition={message.partition}, offset={message.offset}"
                )

            # 4. Call UseCase (Analytics Pipeline)
            output = await self.pipeline.process(pipeline_input)

            # 5. Log result
            elapsed_ms = int((time.perf_counter() - start_time) * 1000)
            if self.logger:
                self.logger.info(
                    f"internal.analytics.delivery.kafka.consumer.handler: Message processed: event_id={event_id}, "
                    f"status={output.processing_status}, elapsed_ms={elapsed_ms}"
                )

        except json.JSONDecodeError as exc:
            # Poison message — log and skip (will commit offset to move forward)
            if self.logger:
                self.logger.error(
                    f"internal.analytics.delivery.kafka.consumer.handler: Invalid JSON: event_id={event_id}, "
                    f"topic={message.topic}, offset={message.offset}, error={exc}"
                )
            # Don't raise — we want to commit offset and skip this message
            return

        except (ErrUAPValidation, ErrUAPVersionUnsupported) as exc:
            # UAP structural validation error — log and skip
            if self.logger:
                self.logger.error(
                    f"internal.analytics.delivery.kafka.consumer.handler: UAP validation error: event_id={event_id}, "
                    f"topic={message.topic}, offset={message.offset}, error={exc}"
                )
            # Don't raise — skip this message
            return

        except ValueError as exc:
            # Validation error (e.g., missing project_id) — log and skip
            if self.logger:
                self.logger.error(
                    f"internal.analytics.delivery.kafka.consumer.handler: Validation error: event_id={event_id}, "
                    f"topic={message.topic}, offset={message.offset}, error={exc}"
                )
            # Don't raise — skip this message
            return

        except Exception as exc:
            # Business/transient error — log and raise (will NOT commit offset, retry on next poll)
            if self.logger:
                self.logger.error(
                    f"internal.analytics.delivery.kafka.consumer.handler: Processing error: event_id={event_id}, "
                    f"topic={message.topic}, offset={message.offset}, error={exc}"
                )
            # Raise to prevent offset commit — message will be retried
            raise

    def _handle_uap(self, envelope: dict):
        # Parse UAP record
        uap_record = UAPRecord.parse(envelope)

        # Extract project_id from UAP
        project_id = uap_record.ingest.project_id if uap_record.ingest else None
        if not project_id:
            self.logger.error(
                f"internal.analytics.delivery.kafka.consumer.handler: Missing project_id in UAP record: {envelope}"
            )
            raise ValueError("Missing project_id in UAP record")

        # Convert to pipeline input
        return to_pipeline_input(uap_record, project_id)


__all__ = ["AnalyticsKafkaHandler"]
