# Phase 7 - Observability and Reliability

## Muc tieu

Dat readiness ve van hanh production: traceability, resilience, va performance.

## Cong viec chinh

1. Structured logging bat buoc fields:
   - trace_id, span_id, run_id, project_id, campaign_id, uap_id
2. Instrument metrics:
   - throughput, latency p50/p95/p99, error rate, lag, outbox backlog
3. Retry/backoff + DLQ policy.
4. Replay tooling theo run_id/event range.
5. Capacity/performance tuning cho batch lon.

## Deliverables

- Dashboard operational.
- Alert rules production.
- Replay CLI/command.

## Test/validation

- Chaos tests (transient DB/Kafka failures).
- Soak test voi volume gan production.
- Recovery test tu DLQ/replay.

## Exit criteria

- SLA latency va reliability dat nguong.
- Oncall runbook kha dung.
