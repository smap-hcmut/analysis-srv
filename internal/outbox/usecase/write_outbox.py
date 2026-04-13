"""outbox/usecase/write_outbox.py — write a pending outbox record to the DB.

The caller is responsible for providing a DB connection within an open
transaction so the outbox write and the business write are atomic.

The `conn` parameter is duck-typed — it must expose an `execute(sql, params)`
method compatible with psycopg2/asyncpg-style raw SQL execution.
"""

from __future__ import annotations

import json

from internal.outbox.type import OutboxRecord

OUTBOX_INSERT_SQL = """
    INSERT INTO analytics_outbox (id, run_id, topic, payload, status, created_at)
    VALUES (%s, %s, %s, %s::jsonb, 'pending', NOW())
    ON CONFLICT (id) DO NOTHING
"""


def write_outbox_record(conn: object, record: OutboxRecord) -> None:
    """Write an OutboxRecord into the outbox table.

    Idempotent — duplicate IDs are silently ignored via ON CONFLICT.
    """
    getattr(conn, "execute")(
        OUTBOX_INSERT_SQL,
        (record.id, record.run_id, record.topic, json.dumps(record.payload)),
    )


__all__ = ["write_outbox_record"]
