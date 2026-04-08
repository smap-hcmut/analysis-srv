# Phase 6 - Contract Publish and Crisis

## Muc tieu

Dam bao tuong thich downstream contracts va kich hoat crisis flow cho project.

## Cong viec chinh

1. Implement publishers cho 3 topics knowledge:
   - analytics.batch.completed
   - analytics.insights.published
   - analytics.report.digest
2. Enforce publish ordering theo run (batch -> insights -> digest).
3. Implement crisis evaluator theo project config.
4. Publish event `project.crisis.detected` khi trigger WARNING/CRITICAL.
5. Implement outbox transaction cho tat ca outbound events.

## Deliverables

- Contract publishers running on staging.
- Crisis alert events co evidence references.

## Test/validation

- Contract tests voi frozen payload fixtures.
- Ordering tests cho publisher.
- Crisis rule scenario tests (negative spike, volume spike, issue pressure, influencer).

## Exit criteria

- Knowledge consume thanh cong khong schema error.
- Crisis event pass validation cua project side.
