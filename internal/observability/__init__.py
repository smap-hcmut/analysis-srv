# observability package — Prometheus metrics (optional dependency)
from internal.observability.metrics import (
    PROMETHEUS_AVAILABLE,
    pipeline_runs_total,
    stage_duration_seconds,
    kafka_publish_total,
    crisis_level_gauge,
)

__all__ = [
    "PROMETHEUS_AVAILABLE",
    "pipeline_runs_total",
    "stage_duration_seconds",
    "kafka_publish_total",
    "crisis_level_gauge",
]
