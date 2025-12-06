# Capability: monitoring

## ADDED Requirements

### Requirement: Prometheus metrics for batch size mismatches

The consumer MUST expose Prometheus metrics tracking when received batch sizes don't match expected sizes (50 for TikTok, 20 for YouTube). The consumer SHALL increment a counter `analytics_batch_size_mismatch_total` when batch size does not match expected size, with labels for `platform`, `expected_size`, and `actual_size`.

**Rationale:**

- Unexpected batch sizes indicate crawler assembly bugs
- Log-only tracking prevents automated alerting
- Trending helps detect gradual degradation

#### Scenario: Batch with unexpected size increments metric

**Given:**

- Consumer receives batch from TikTok crawler
- Batch contains 45 items (expected: 50)
- Prometheus metrics endpoint is enabled

**When:**

- Consumer processes batch

**Then:**

- Log warning is emitted (existing behavior)
- Prometheus counter `analytics_batch_size_mismatch_total` increments
- Metric has labels: `platform="tiktok"`, `expected_size="50"`, `actual_size="45"`
- Metric is exposed at `:9090/metrics`

**Acceptance:**

```python
# internal/consumers/metrics.py (NEW FILE)
from prometheus_client import Counter

batch_size_mismatch_total = Counter(
    'analytics_batch_size_mismatch_total',
    'Total number of batches with unexpected size',
    ['platform', 'expected_size', 'actual_size']
)

# internal/consumers/main.py:192-199 (MODIFIED)
if len(batch_items) != expected_size:
    logger.warning(
        "Unexpected batch size: expected=%d, actual=%d, platform=%s",
        expected_size, len(batch_items), platform
    )
    # ADD:
    from internal.consumers.metrics import batch_size_mismatch_total
    batch_size_mismatch_total.labels(
        platform=platform,
        expected_size=str(expected_size),
        actual_size=str(len(batch_items))
    ).inc()
```

**Metric Query Examples:**

```promql
# Total mismatches in last 5 minutes
rate(analytics_batch_size_mismatch_total[5m])

# Mismatches by platform
sum(analytics_batch_size_mismatch_total) by (platform)

# Alert on high mismatch rate
rate(analytics_batch_size_mismatch_total[5m]) > 0.1
```

**Validation:**

```bash
# Send test event with incorrect batch size
# Then check metrics
curl http://localhost:9090/metrics | grep analytics_batch_size_mismatch_total

# Should show:
# analytics_batch_size_mismatch_total{platform="tiktok",expected_size="50",actual_size="45"} 1.0
```

---

### Requirement: Prometheus metrics endpoint exposure

The consumer service MUST expose Prometheus metrics on port 9090 (configurable via `metrics_port` setting) for scraping by Prometheus server. The endpoint SHALL be accessible at `http://localhost:{metrics_port}/metrics`, MUST return Prometheus text format, and SHALL include batch size mismatch metrics when `metrics_enabled = true`.

#### Scenario: Metrics endpoint is accessible

**Given:**

- Consumer service is running
- `metrics_enabled = true` in settings
- `metrics_port = 9090` in settings

**When:**

- HTTP GET request to `http://localhost:9090/metrics`

**Then:**

- Response status is 200 OK
- Response contains Prometheus text format
- Batch size mismatch metrics are included
- Standard Python metrics are included (process*\*, python*\*)

**Acceptance:**

```bash
# Verify metrics endpoint
curl -s http://localhost:9090/metrics | head -20

# Should include:
# # HELP analytics_batch_size_mismatch_total Total batches with unexpected size
# # TYPE analytics_batch_size_mismatch_total counter
# analytics_batch_size_mismatch_total{...} 0.0
```

**Configuration:**

```python
# core/config.py (already exists)
metrics_enabled: bool = True
metrics_port: int = 9090
```

---

## Cross-References

- **Related to:** `service_lifecycle` (metrics exposed during consumer runtime)
- **Related to:** `foundation` (database performance impacts batch processing)

## Implementation Notes

### Prometheus Client Integration

The Prometheus client library is already included in dependencies. Metrics are automatically exposed via HTTP endpoint when imported.

**No additional configuration needed** - importing `prometheus_client` and defining metrics is sufficient.

### Metric Naming Conventions

Following Prometheus best practices:

- Metric name: `analytics_batch_size_mismatch_total` (subsystem_feature_unit)
- Type: Counter (monotonically increasing, never decreases)
- Labels: dimension for filtering (platform, sizes)

### Performance Overhead

- **Counter increment:** <1 microsecond
- **Memory per label combination:** ~40 bytes
- **Worst case:** 2 platforms × 5 expected sizes × 10 actual sizes = 100 combinations = 4 KB
- **Conclusion:** Negligible overhead

### Alerting Examples

```yaml
# Prometheus alerting rules
groups:
  - name: analytics_batch_processing
    rules:
      - alert: HighBatchSizeMismatch
        expr: rate(analytics_batch_size_mismatch_total[5m]) > 0.1
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "High rate of batch size mismatches"
          description: "{{ $value }} batches/sec have incorrect sizes"

      - alert: CrawlerBatchAssemblyFailure
        expr: sum(rate(analytics_batch_size_mismatch_total[5m])) by (platform) > 0.5
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "Crawler {{ $labels.platform }} producing incorrect batch sizes"
```
