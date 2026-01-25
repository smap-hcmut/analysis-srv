# Design: Fix Collector Message Format

## Context

Analytics Engine publish analyze results đến Collector service qua RabbitMQ. Collector sử dụng message này để:

1. Track analyze progress (`analyze_done`, `analyze_errors`)
2. Check completion và send webhook
3. Update project state trong Redis

Contract spec định nghĩa flat message format, nhưng implementation hiện tại gửi nested format.

## Goals / Non-Goals

**Goals:**

- Align message format với Collector contract spec
- Ensure `project_id` luôn non-empty khi publish
- Maintain backward compatibility trong internal code (logging, debugging)

**Non-Goals:**

- Thay đổi Collector code
- Thay đổi RabbitMQ exchange/routing configuration
- Thay đổi business logic của analytics processing

## Decisions

### Decision 1: Deprecate `AnalyzeResultMessage` wrapper

**What:** Remove hoặc deprecate `AnalyzeResultMessage` class, sử dụng `AnalyzeResultPayload` trực tiếp.

**Why:**

- Collector không expect wrapper `success` field
- Simplify code path
- Reduce confusion về message structure

**Alternative considered:**

- Keep wrapper nhưng flatten trong `to_dict()` → Rejected vì confusing, class name không reflect output

### Decision 2: Keep `results`/`errors` arrays internal-only

**What:** Giữ `results` và `errors` fields trong dataclass nhưng exclude từ `to_dict()` output.

**Why:**

- Useful cho internal logging và debugging
- Không break existing code sử dụng fields này
- Collector không cần chi tiết từng item

**Alternative considered:**

- Remove fields hoàn toàn → Rejected vì mất debugging capability

### Decision 3: Validate `project_id` before publish

**What:** Add validation trong publisher, skip publish nếu `project_id` empty.

**Why:**

- Contract require non-empty `project_id`
- Collector sẽ reject message thiếu `project_id`
- Better to fail fast với clear error log

## Message Format Comparison

### Contract Spec (Target)

```json
{
  "project_id": "proj123",
  "job_id": "proj123-brand-0-analyze-batch-1",
  "task_type": "analyze_result",
  "batch_size": 10,
  "success_count": 8,
  "error_count": 2
}
```

### Current Implementation (Wrong)

```json
{
  "success": true,
  "payload": {
    "project_id": "proj123",
    "job_id": "proj123-brand-0",
    "task_type": "analyze_result",
    "batch_size": 50,
    "success_count": 48,
    "error_count": 2,
    "results": [...],
    "errors": [...]
  }
}
```

### New Implementation (Correct)

```json
{
  "project_id": "proj123",
  "job_id": "proj123-brand-0",
  "task_type": "analyze_result",
  "batch_size": 50,
  "success_count": 48,
  "error_count": 2
}
```

## Code Changes Overview

### 1. `models/messages.py`

```python
@dataclass
class AnalyzeResultPayload:
    """Flat payload for Collector consumption.

    Message format follows collector-crawler-contract.md Section 3.
    """
    project_id: str  # Required, non-empty
    job_id: str
    task_type: str = "analyze_result"
    batch_size: int = 0
    success_count: int = 0
    error_count: int = 0
    # Internal-only fields (not serialized to Collector)
    _results: List[AnalyzeItem] = field(default_factory=list, repr=False)
    _errors: List[AnalyzeError] = field(default_factory=list, repr=False)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to flat dictionary for Collector."""
        return {
            "project_id": self.project_id,
            "job_id": self.job_id,
            "task_type": self.task_type,
            "batch_size": self.batch_size,
            "success_count": self.success_count,
            "error_count": self.error_count,
        }
```

### 2. `infrastructure/messaging/publisher.py`

```python
async def publish_analyze_result(self, payload: AnalyzeResultPayload) -> None:
    """Publish analyze result to Collector.

    Args:
        payload: Flat payload matching Collector contract

    Raises:
        RabbitMQPublisherError: If project_id is empty or publish fails
    """
    if not payload.project_id:
        raise RabbitMQPublisherError("project_id is required for publishing")

    message_bytes = payload.to_bytes()
    await self._publish(message_bytes)
```

### 3. `internal/consumers/main.py`

```python
async def _publish_batch_result(...):
    if not project_id:
        logger.error("Cannot publish result: project_id is required")
        return

    payload = AnalyzeResultPayload(
        project_id=project_id,
        job_id=job_id,
        task_type="analyze_result",
        batch_size=batch_size,
        success_count=success_count,
        error_count=error_count,
    )
    await publisher.publish_analyze_result(payload)
```

## Risks / Trade-offs

| Risk                                | Mitigation                                                        |
| ----------------------------------- | ----------------------------------------------------------------- |
| Breaking change với Collector       | Collector đã expect flat format, change này align với expectation |
| Loss of detailed results in message | Keep internal fields cho logging, Collector không cần             |
| Empty project_id edge case          | Add validation, log error, skip publish                           |

## Migration Plan

1. Update `models/messages.py` - change dataclass structure
2. Update `infrastructure/messaging/publisher.py` - accept flat payload
3. Update `internal/consumers/main.py` - build flat payload
4. Update tests
5. Deploy và verify với Collector trong staging

**Rollback:** Revert code changes, no data migration needed.

## Open Questions

None - contract spec is clear.
