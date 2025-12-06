"""Prometheus metrics for Analytics Engine consumer.

This module provides metrics for monitoring batch processing,
error rates, and performance characteristics.
"""

from prometheus_client import Counter, Histogram, Gauge

# Batch size mismatch tracking
batch_size_mismatch_total = Counter(
    "analytics_batch_size_mismatch_total",
    "Total number of batches with unexpected size",
    ["platform", "expected_size", "actual_size"],
)

# Batch processing metrics
batch_processing_total = Counter(
    "analytics_batch_processing_total", "Total number of batches processed", ["platform", "status"]
)

batch_processing_duration_seconds = Histogram(
    "analytics_batch_processing_duration_seconds",
    "Time spent processing a batch",
    ["platform"],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0],
)

# Item processing metrics
items_processed_total = Counter(
    "analytics_items_processed_total", "Total number of items processed", ["platform", "status"]
)

# Error tracking
processing_errors_total = Counter(
    "analytics_processing_errors_total",
    "Total number of processing errors",
    ["platform", "error_category"],
)

# Active processing gauge
active_batches = Gauge("analytics_active_batches", "Number of batches currently being processed")
