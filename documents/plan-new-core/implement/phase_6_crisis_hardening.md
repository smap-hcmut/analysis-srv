# Phase 6 — Crisis Detection, Outbox Pattern, Observability, Replay

> **Depends on:** Phase 5 (full pipeline end-to-end working)
> **This is a hardening phase — no new core-analysis features, all cross-cutting concerns**

## Mục tiêu

1. **Crisis detection** — rule-based scoring trên `TopIssueRow[]` + `ThreadControversyRow[]`
2. **Outbox pattern** — đảm bảo at-least-once delivery cho 3 Kafka topics
3. **Observability** — metrics, structured logging, run manifest persistence
4. **Replay tool** — re-run pipeline cho một batch đã ingest (debugging + reprocessing)

## 6.1 Crisis Detection

### Folder structure

```
internal/crisis/
├── interface.py
├── type.py         # CrisisSignal, CrisisLevel, CrisisAssessment
├── constant.py     # thresholds
├── errors.py
└── usecase/
    ├── new.py
    ├── usecase.py
    ├── assess_crisis.py    # main scorer
    └── helpers.py
```

### `type.py`

```python
# internal/crisis/type.py
from dataclasses import dataclass, field
from typing import Literal

CrisisLevel = Literal["none", "watch", "warning", "critical"]

@dataclass
class CrisisSignal:
    signal_type: str                # "issue_pressure", "controversy_spike", "sentiment_collapse"
    severity: str                   # "low"/"medium"/"high"/"critical_like_proxy"
    evidence_value: float           # pressure score, controversy score, etc.
    threshold_used: float
    evidence_references: list[str]  # mention_ids

@dataclass
class CrisisAssessment:
    run_id: str
    project_id: str
    campaign_id: str
    crisis_level: CrisisLevel
    signals: list[CrisisSignal] = field(default_factory=list)
    top_issue_category: str | None = None
    top_issue_pressure: float = 0.0
    top_controversy_score: float = 0.0
    composite_crisis_score: float = 0.0
```

### `constant.py`

```python
# internal/crisis/constant.py

# Issue pressure thresholds
ISSUE_PRESSURE_WATCH      = 5.0
ISSUE_PRESSURE_WARNING    = 12.0
ISSUE_PRESSURE_CRITICAL   = 25.0

# Thread controversy thresholds
CONTROVERSY_WATCH         = 0.45
CONTROVERSY_WARNING       = 0.65
CONTROVERSY_CRITICAL      = 0.80

# Sentiment collapse: proportion of negative mentions
SENTIMENT_COLLAPSE_WATCH    = 0.40
SENTIMENT_COLLAPSE_WARNING  = 0.60
SENTIMENT_COLLAPSE_CRITICAL = 0.75

# Critical severity issue multiplier (critical_like_proxy → ×1.8 weight)
CRITICAL_SEVERITY_MULTIPLIER = 1.8
```

### `assess_crisis.py`

```python
# internal/crisis/usecase/assess_crisis.py

from smap.bi.models import BIReportBundle
from internal.crisis.type import CrisisAssessment, CrisisLevel, CrisisSignal
from internal.crisis import constant as C

def assess_crisis(
    run_id: str,
    project_id: str,
    campaign_id: str,
    reports: BIReportBundle,
) -> CrisisAssessment:
    """
    Rule-based crisis scoring — no ML.
    Inputs: BIReportBundle.top_issues_report + thread_controversy_report + buzz_report
    """
    signals: list[CrisisSignal] = []

    # --- Signal 1: Issue pressure ---
    if reports.top_issues_report.issues:
        top_issue = reports.top_issues_report.issues[0]
        pressure = top_issue.issue_pressure_proxy
        if pressure >= C.ISSUE_PRESSURE_WATCH:
            signals.append(CrisisSignal(
                signal_type="issue_pressure",
                severity=_pressure_to_severity(pressure),
                evidence_value=pressure,
                threshold_used=C.ISSUE_PRESSURE_WATCH,
                evidence_references=top_issue.evidence_references,
            ))

    # --- Signal 2: Thread controversy spike ---
    if reports.thread_controversy_report.threads:
        top_thread = reports.thread_controversy_report.threads[0]
        score = top_thread.controversy_score_proxy
        if score >= C.CONTROVERSY_WATCH:
            signals.append(CrisisSignal(
                signal_type="controversy_spike",
                severity=_controversy_to_severity(score),
                evidence_value=score,
                threshold_used=C.CONTROVERSY_WATCH,
                evidence_references=top_thread.evidence_references,
            ))

    # --- Signal 3: Sentiment collapse ---
    neg_count, total = _count_sentiment(reports)
    if total > 0:
        neg_ratio = neg_count / total
        if neg_ratio >= C.SENTIMENT_COLLAPSE_WATCH:
            signals.append(CrisisSignal(
                signal_type="sentiment_collapse",
                severity=_neg_ratio_to_severity(neg_ratio),
                evidence_value=round(neg_ratio, 4),
                threshold_used=C.SENTIMENT_COLLAPSE_WATCH,
                evidence_references=[],
            ))

    composite = _composite_score(signals)
    level = _crisis_level(composite, signals)

    top_issue = reports.top_issues_report.issues[0] if reports.top_issues_report.issues else None
    top_thread = reports.thread_controversy_report.threads[0] if reports.thread_controversy_report.threads else None

    return CrisisAssessment(
        run_id=run_id,
        project_id=project_id,
        campaign_id=campaign_id,
        crisis_level=level,
        signals=signals,
        top_issue_category=top_issue.issue_category if top_issue else None,
        top_issue_pressure=top_issue.issue_pressure_proxy if top_issue else 0.0,
        top_controversy_score=top_thread.controversy_score_proxy if top_thread else 0.0,
        composite_crisis_score=composite,
    )


def _pressure_to_severity(pressure: float) -> str:
    if pressure >= C.ISSUE_PRESSURE_CRITICAL:
        return "critical_like_proxy"
    if pressure >= C.ISSUE_PRESSURE_WARNING:
        return "high"
    return "medium"


def _controversy_to_severity(score: float) -> str:
    if score >= C.CONTROVERSY_CRITICAL:
        return "critical_like_proxy"
    if score >= C.CONTROVERSY_WARNING:
        return "high"
    return "medium"


def _neg_ratio_to_severity(ratio: float) -> str:
    if ratio >= C.SENTIMENT_COLLAPSE_CRITICAL:
        return "high"
    if ratio >= C.SENTIMENT_COLLAPSE_WARNING:
        return "medium"
    return "low"


def _composite_score(signals: list[CrisisSignal]) -> float:
    weight_map = {"low": 0.3, "medium": 1.0, "high": 1.8, "critical_like_proxy": 2.5}
    return round(sum(weight_map.get(s.severity, 1.0) for s in signals), 4)


def _crisis_level(composite: float, signals: list[CrisisSignal]) -> CrisisLevel:
    if any(s.severity == "critical_like_proxy" for s in signals) or composite >= 5.0:
        return "critical"
    if composite >= 2.5:
        return "warning"
    if composite >= 0.8:
        return "watch"
    return "none"


def _count_sentiment(reports: BIReportBundle) -> tuple[int, int]:
    """Approximate negative ratio from SOVReport or BuzzReport proxy."""
    # Note: Phase 6 does not have direct access to sentiment_facts here.
    # Use buzz_report entity rows as proxy: sum delta_mention_count negative entities.
    # Full implementation: pass fact_sentiment DataFrame directly.
    return 0, 0   # stub — implement by joining fact_sentiment from MartBundle
```

**Integration note:** Pass `MartBundle` as well as `BIReportBundle` to `assess_crisis()` to enable the full sentiment collapse signal via `mart.tables["fact_sentiment"]`.

## 6.2 Outbox Pattern

Crisis messages and run manifests must be durably stored before Kafka publish to prevent silent loss.

### Strategy

- **Outbox table in Postgres:** `analytics_outbox` with columns:
  `id (UUID PK), run_id, topic, payload (jsonb), status (pending/sent/failed), created_at, sent_at`
- **Transactional write:** Write outbox row in same DB transaction as run_manifest row
- **Relay loop:** Background task polls `WHERE status='pending' ORDER BY created_at LIMIT 50`, publishes to Kafka, marks as `sent`
- **Retry:** Failed Kafka publishes stay `pending`, retried after backoff
- **Retention:** Purge `sent` rows older than 7 days

### Folder structure

```
internal/outbox/
├── interface.py
├── type.py          # OutboxRecord, OutboxStatus
├── constant.py      # TABLE_NAME, RELAY_BATCH_SIZE, RETENTION_DAYS
├── errors.py        # OutboxWriteError, OutboxRelayError
└── usecase/
    ├── new.py
    ├── usecase.py
    ├── write_outbox.py    # write_outbox_record()
    ├── relay_outbox.py    # relay_pending_records() — called from background worker
    └── helpers.py
```

### `type.py`

```python
# internal/outbox/type.py
from dataclasses import dataclass
from datetime import datetime
from typing import Literal
import uuid

OutboxStatus = Literal["pending", "sent", "failed"]

@dataclass
class OutboxRecord:
    id: str
    run_id: str
    topic: str
    payload: dict
    status: OutboxStatus = "pending"
    created_at: datetime | None = None
    sent_at: datetime | None = None
    error: str | None = None

    @classmethod
    def new(cls, run_id: str, topic: str, payload: dict) -> "OutboxRecord":
        return cls(id=str(uuid.uuid4()), run_id=run_id, topic=topic, payload=payload)
```

### `write_outbox.py`

```python
# internal/outbox/usecase/write_outbox.py

import json
from internal.outbox.type import OutboxRecord
from pkg.postgres import PostgresClient  # existing pkg

OUTBOX_INSERT_SQL = """
    INSERT INTO analytics_outbox (id, run_id, topic, payload, status, created_at)
    VALUES (%s, %s, %s, %s::jsonb, 'pending', NOW())
"""

def write_outbox_record(conn, record: OutboxRecord) -> None:
    """Write outbox record within caller's transaction."""
    conn.execute(OUTBOX_INSERT_SQL, (
        record.id,
        record.run_id,
        record.topic,
        json.dumps(record.payload),
    ))
```

### `relay_outbox.py`

```python
# internal/outbox/usecase/relay_outbox.py
# Called from a background asyncio task every RELAY_INTERVAL_SECONDS

from internal.outbox.constant import RELAY_BATCH_SIZE, RELAY_INTERVAL_SECONDS

POLL_SQL = """
    SELECT id, run_id, topic, payload FROM analytics_outbox
    WHERE status = 'pending'
    ORDER BY created_at ASC
    LIMIT %s
    FOR UPDATE SKIP LOCKED
"""

MARK_SENT_SQL = "UPDATE analytics_outbox SET status='sent', sent_at=NOW() WHERE id=%s"
MARK_FAILED_SQL = "UPDATE analytics_outbox SET status='failed', error=%s WHERE id=%s"

def relay_pending_records(conn, kafka_producer) -> int:
    """
    Poll up to RELAY_BATCH_SIZE pending records, publish to Kafka.
    Returns count of successfully relayed records.
    """
    with conn.transaction():
        rows = conn.execute(POLL_SQL, (RELAY_BATCH_SIZE,)).fetchall()
        relayed = 0
        for row in rows:
            try:
                kafka_producer.produce(topic=row["topic"], value=row["payload"])
                kafka_producer.flush()
                conn.execute(MARK_SENT_SQL, (row["id"],))
                relayed += 1
            except Exception as exc:
                conn.execute(MARK_FAILED_SQL, (str(exc), row["id"]))
        return relayed
```

### Migration SQL

```sql
-- migrations/0XX_create_analytics_outbox.sql
CREATE TABLE IF NOT EXISTS analytics_outbox (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id      TEXT NOT NULL,
    topic       TEXT NOT NULL,
    payload     JSONB NOT NULL,
    status      TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'sent', 'failed')),
    error       TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    sent_at     TIMESTAMPTZ
);
CREATE INDEX idx_outbox_pending ON analytics_outbox (status, created_at)
    WHERE status = 'pending';
```

## 6.3 Observability

### Structured logging conventions

```python
# All pipeline log entries use this structure:
import structlog
log = structlog.get_logger()

# At stage start:
log.info("stage.start", run_id=run_id, stage="enrichment", mention_count=len(mentions))

# At stage end:
log.info("stage.done", run_id=run_id, stage="enrichment",
         elapsed_ms=elapsed, entity_facts=len(bundle.entity_facts),
         topic_facts=len(bundle.topic_facts))

# At publish:
log.info("publish.ok", run_id=run_id, topic="smap.analytics.nlp",
         message_count=len(layer3_msgs))

# On error:
log.error("stage.error", run_id=run_id, stage="enrichment",
          error=str(exc), exc_info=True)
```

### Run manifest persistence

```python
# internal/runtime/usecase/run_manifest.py
# Port từ core-analysis/src/smap/run_manifest.py

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
import json

@dataclass
class StageTimings:
    stage: str
    started_at: str
    ended_at: str
    elapsed_ms: float
    record_count: int
    error: str | None = None

@dataclass
class RunManifest:
    run_id: str
    project_id: str
    campaign_id: str
    started_at: str
    ended_at: str | None = None
    status: str = "running"       # "running"/"completed"/"failed"
    mention_count: int = 0
    enrichment_versions: dict = field(default_factory=dict)
    stage_timings: list[StageTimings] = field(default_factory=list)
    error: str | None = None

def save_run_manifest(conn, manifest: RunManifest) -> None:
    """Upsert run manifest to postgres analytics_run_manifest table."""
    conn.execute(
        """
        INSERT INTO analytics_run_manifest (run_id, project_id, campaign_id, data, updated_at)
        VALUES (%s, %s, %s, %s::jsonb, NOW())
        ON CONFLICT (run_id) DO UPDATE SET data=EXCLUDED.data, updated_at=NOW()
        """,
        (manifest.run_id, manifest.project_id, manifest.campaign_id,
         json.dumps(asdict(manifest))),
    )
```

### Migration SQL

```sql
-- migrations/0XY_create_analytics_run_manifest.sql
CREATE TABLE IF NOT EXISTS analytics_run_manifest (
    run_id      TEXT PRIMARY KEY,
    project_id  TEXT NOT NULL,
    campaign_id TEXT NOT NULL,
    data        JSONB NOT NULL,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_run_manifest_project ON analytics_run_manifest (project_id, campaign_id);
```

### Prometheus metrics (optional)

Expose via existing HTTP server using `prometheus_client`:

```python
# internal/observability/metrics.py
from prometheus_client import Counter, Histogram, Gauge

pipeline_runs_total        = Counter("analysis_pipeline_runs_total", "Total pipeline runs", ["status"])
stage_duration_seconds     = Histogram("analysis_stage_duration_seconds", "Stage duration", ["stage"])
kafka_publish_total        = Counter("analysis_kafka_publish_total", "Kafka messages published", ["topic", "status"])
crisis_level_gauge         = Gauge("analysis_crisis_level", "Current crisis level (0=none,1=watch,2=warning,3=critical)", ["project_id"])
```

## 6.4 Replay Tool

A CLI tool to re-run the pipeline for a batch that was already ingested, useful for:
- Debugging enrichment issues
- Re-running after model update
- Backfilling old data

### `tools/replay_batch.py`

```python
#!/usr/bin/env python3
"""
Replay pipeline for a historical batch.

Usage:
    python tools/replay_batch.py \
        --project-id proj_123 \
        --campaign-id camp_456 \
        --kafka-group-offset 1000 \
        --dry-run

Options:
    --run-id         Use a specific run_id (default: generate new)
    --from-manifest  Re-run from an existing run_id's manifest
    --dry-run        Run pipeline but do not publish to Kafka
    --skip-publish   Alias for --dry-run
"""
import argparse
import sys
from internal.pipeline.usecase.run_pipeline import run_pipeline
from internal.pipeline.type import PipelineInput, PipelineConfig
from internal.runtime.usecase.run_id import default_run_id

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--campaign-id", required=True)
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--input-file", default=None,
                        help="JSON file with UAP records (if not re-reading from Kafka)")
    args = parser.parse_args()

    run_id = args.run_id or default_run_id()

    config = PipelineConfig(
        dry_run=args.dry_run,
        enrichment_enabled=True,
        reporting_enabled=True,
    )

    # Load records from file or Postgres replay table
    records = _load_records(args)
    if not records:
        print("No records found for replay.", file=sys.stderr)
        sys.exit(1)

    inp = PipelineInput(
        run_id=run_id,
        project_id=args.project_id,
        campaign_id=args.campaign_id,
        uap_records=records,
    )

    result = run_pipeline(inp, config)
    print(f"Replay complete. run_id={run_id} status={result.status} "
          f"mentions={result.mention_count} "
          f"published={result.published_count if not args.dry_run else 'skipped (dry-run)'}")


def _load_records(args):
    if args.input_file:
        import json
        with open(args.input_file) as f:
            return json.load(f)
    # TODO: load from Postgres replay_batch table or Kafka consumer backfill
    return []


if __name__ == "__main__":
    main()
```

### Replay batch table (optional — for production replay)

```sql
-- migrations/0XZ_create_analytics_replay_batch.sql
CREATE TABLE IF NOT EXISTS analytics_replay_batch (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id  TEXT NOT NULL,
    campaign_id TEXT NOT NULL,
    run_id      TEXT,               -- populated after replay starts
    records     JSONB NOT NULL,     -- serialized UAPRecord[]
    status      TEXT NOT NULL DEFAULT 'queued' CHECK (status IN ('queued','running','done','failed')),
    requested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);
```

## Summary — what Phase 6 adds

| Concern | Before Phase 6 | After Phase 6 |
|---|---|---|
| Crisis detection | None | Rule-based 3-signal scorer, `CrisisLevel` enum |
| Kafka delivery | Best-effort (fire-and-forget) | Outbox table → at-least-once relay |
| Observability | Ad-hoc print/log | Structured logs, `RunManifest` in Postgres |
| Debugging | Manual Kafka consumer | `replay_batch.py` CLI with `--dry-run` |
| Run tracking | None | `analytics_run_manifest` table |

## Gate Phase 6

- [ ] `assess_crisis()` returns `CrisisLevel.warning` for batch with issue_pressure > 12
- [ ] Outbox relay: simulated Kafka failure → record stays `pending`, retried on next cycle
- [ ] `RunManifest` persisted to Postgres after each complete run
- [ ] `replay_batch.py --dry-run` completes without Kafka publish for sample JSON input
- [ ] Structured log entries contain `run_id` on every line (verified via `grep run_id`)
- [ ] All 3 DB migrations apply cleanly on fresh schema
