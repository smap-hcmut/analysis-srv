"""outbox/usecase/relay_outbox.py — poll pending records and publish to Kafka.

Designed for a background worker loop.  The `conn` parameter is a synchronous
DB connection with `execute()` / `fetchall()` and `transaction()` context
manager.  The `producer` must expose `send(topic, value: bytes)` synchronously
(wrap async if needed at the call site).
"""

from __future__ import annotations

import json

from loguru import logger

from internal.outbox.constant import RELAY_BATCH_SIZE
from internal.outbox.type import RelayResult

POLL_SQL = """
    SELECT id, run_id, topic, payload
    FROM analytics_outbox
    WHERE status = 'pending'
    ORDER BY created_at ASC
    LIMIT %s
    FOR UPDATE SKIP LOCKED
"""

MARK_SENT_SQL = "UPDATE analytics_outbox SET status='sent', sent_at=NOW() WHERE id=%s"
MARK_FAILED_SQL = "UPDATE analytics_outbox SET status='failed', error=%s WHERE id=%s"


def relay_pending_records(conn: object, producer: object) -> RelayResult:
    """Poll up to RELAY_BATCH_SIZE pending records and publish to Kafka.

    Returns a RelayResult with counts of attempted / sent / failed.
    """
    result = RelayResult()

    with getattr(conn, "transaction")():
        rows = getattr(conn, "execute")(POLL_SQL, (RELAY_BATCH_SIZE,)).fetchall()
        for row in rows:
            result.attempted += 1
            try:
                payload_bytes = json.dumps(row["payload"]).encode()
                getattr(producer, "send")(topic=row["topic"], value=payload_bytes)
                getattr(conn, "execute")(MARK_SENT_SQL, (row["id"],))
                result.sent += 1
                logger.debug(
                    "outbox: relayed",
                    record_id=row["id"],
                    topic=row["topic"],
                )
            except Exception as exc:
                getattr(conn, "execute")(MARK_FAILED_SQL, (str(exc), row["id"]))
                result.failed += 1
                logger.error(
                    "outbox: relay failed",
                    record_id=row["id"],
                    topic=row["topic"],
                    error=str(exc),
                )

    return result


__all__ = ["relay_pending_records"]
