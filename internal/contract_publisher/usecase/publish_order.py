"""Enforce contract-required publish ordering.

Contract mandate (contract.md Section "Publish order obligation"):
    1. analytics.batch.completed    — Layer 3 (full documents[])
    2. analytics.insights.published — Layer 2 (one message per card)
    3. analytics.report.digest      — Layer 1 (MUST be last — triggers export)

Knowledge-srv uses the digest as its "run complete" signal. If digest arrives
before batch/insights, the NotebookLM export will be triggered prematurely.
"""

import json
from typing import Any, Optional

from pkg.kafka.interface import IKafkaProducer
from pkg.logger.logger import Logger
from internal.contract_publisher.constant import (
    TOPIC_BATCH_COMPLETED,
    TOPIC_INSIGHTS_PUBLISHED,
    TOPIC_REPORT_DIGEST,
)
from internal.contract_publisher.errors import KafkaPublishError


async def publish_in_required_order(
    batch_payload: dict,
    insight_payloads: list[dict],
    digest_payload: dict,
    kafka_producer: IKafkaProducer,
    logger: Optional[Logger] = None,
) -> None:
    """Publish all 3 topics in contract-required order.

    Raises KafkaPublishError on first failure — caller decides retry strategy.
    """
    # 1. Layer 3 — batch.completed (potentially large ~4MB)
    await _send(
        kafka_producer=kafka_producer,
        topic=TOPIC_BATCH_COMPLETED,
        key=batch_payload.get("project_id", ""),
        payload=batch_payload,
    )
    if logger:
        logger.info(
            f"internal.contract_publisher: analytics.batch.completed published "
            f"doc_count={len(batch_payload.get('documents', []))}, "
            f"project_id={batch_payload.get('project_id')}"
        )

    # 2. Layer 2 — insights.published (one message per card, may be 0)
    run_id = digest_payload.get("run_id", "")
    for card in insight_payloads:
        await _send(
            kafka_producer=kafka_producer,
            topic=TOPIC_INSIGHTS_PUBLISHED,
            key=run_id,
            payload=card,
        )
    if logger and insight_payloads:
        logger.info(
            f"internal.contract_publisher: analytics.insights.published "
            f"count={len(insight_payloads)}, run_id={run_id}"
        )

    # 3. Layer 1 — report.digest (MUST be last)
    await _send(
        kafka_producer=kafka_producer,
        topic=TOPIC_REPORT_DIGEST,
        key=run_id,
        payload=digest_payload,
    )
    if logger:
        logger.info(
            f"internal.contract_publisher: analytics.report.digest published "
            f"run_id={run_id} — run complete"
        )


async def _send(
    kafka_producer: IKafkaProducer,
    topic: str,
    key: str,
    payload: dict,
) -> None:
    """Serialize payload to JSON bytes and send to Kafka topic."""
    try:
        value_bytes = json.dumps(payload, ensure_ascii=False, default=str).encode(
            "utf-8"
        )
        key_bytes = key.encode("utf-8") if key else None
        await kafka_producer.send(
            topic=topic,
            value=value_bytes,
            key=key_bytes,
        )
    except Exception as exc:
        raise KafkaPublishError(topic=topic, cause=exc) from exc


__all__ = ["publish_in_required_order"]
