"""observability/metrics.py — Prometheus metrics with graceful fallback.

If prometheus_client is not installed, all metrics are replaced with no-op
stubs so the rest of the codebase can import unconditionally.
"""

try:
    from prometheus_client import Counter, Histogram, Gauge

    pipeline_runs_total = Counter(
        "analysis_pipeline_runs_total",
        "Total pipeline runs",
        ["status"],
    )
    stage_duration_seconds = Histogram(
        "analysis_stage_duration_seconds",
        "Stage wall-clock duration in seconds",
        ["stage"],
    )
    kafka_publish_total = Counter(
        "analysis_kafka_publish_total",
        "Total messages published to Kafka",
        ["topic", "status"],
    )
    crisis_level_gauge = Gauge(
        "analysis_crisis_level",
        "Current crisis level (0=none, 1=watch, 2=warning, 3=critical)",
        ["project_id"],
    )

    PROMETHEUS_AVAILABLE = True

except ImportError:
    PROMETHEUS_AVAILABLE = False

    class _Noop:  # pragma: no cover
        """Stub that silently accepts all metric calls."""

        def labels(self, **kwargs: object) -> "_Noop":
            return self

        def inc(self, *args: object, **kwargs: object) -> None:
            pass

        def observe(self, *args: object, **kwargs: object) -> None:
            pass

        def set(self, *args: object, **kwargs: object) -> None:
            pass

    pipeline_runs_total = _Noop()  # type: ignore[assignment]
    stage_duration_seconds = _Noop()  # type: ignore[assignment]
    kafka_publish_total = _Noop()  # type: ignore[assignment]
    crisis_level_gauge = _Noop()  # type: ignore[assignment]


__all__ = [
    "PROMETHEUS_AVAILABLE",
    "pipeline_runs_total",
    "stage_duration_seconds",
    "kafka_publish_total",
    "crisis_level_gauge",
]
