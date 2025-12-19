# Design: Result Publisher for Collector Integration

## Context

Analytics Engine cần gửi kết quả phân tích về Collector service để:

1. Collector track tiến độ analyze (success_count, error_count)
2. Collector notify webhook về progress/completion
3. Hoàn thành integration flow: Crawler → Analytics → Collector → Project

### Current Flow (Incomplete)

```
Crawler ──(data.collected)──► Analytics ──(save to DB)──► ✗ (no notification to Collector)
```

### Target Flow (Complete)

```
Crawler ──(data.collected)──► Analytics ──(analyze.result)──► Collector ──(webhook)──► Project
```

## Goals / Non-Goals

### Goals

- Implement RabbitMQ publisher để gửi `analyze.result` messages
- Follow exact message format từ integration contract
- Handle partial failures (some items success, some error)
- Handle complete failures (MinIO fetch error)

### Non-Goals

- Retry logic cho failed publishes (sẽ implement sau nếu cần)
- Message deduplication (Collector handles idempotency)
- Batch result aggregation across multiple batches

## Decisions

### Decision 1: Reuse existing RabbitMQ connection

**What**: Publisher sẽ share connection với Consumer thay vì tạo connection riêng.

**Why**:

- Giảm resource usage (1 connection thay vì 2)
- Simpler lifecycle management
- aio-pika supports multiple channels per connection

**Alternative considered**: Separate connection cho publisher

- Rejected: Unnecessary complexity, no isolation benefit

### Decision 2: Message format follows integration contract exactly

**What**: Sử dụng exact JSON structure từ `document/integration-analytics-service.md`

```python
@dataclass
class AnalyzeResultMessage:
    success: bool
    payload: AnalyzeResultPayload

@dataclass
class AnalyzeResultPayload:
    project_id: str
    job_id: str
    task_type: str  # Always "analyze_result"
    batch_size: int
    success_count: int
    error_count: int
    results: List[AnalyzeItem]  # Optional, có thể empty
    errors: List[AnalyzeError]  # Optional, có thể empty
```

**Why**: Collector đã implement handler theo contract này

### Decision 3: Publish after all items processed

**What**: Gửi 1 message per batch sau khi tất cả items đã được process

**Why**:

- Giảm message volume (1 message thay vì N messages)
- Collector có thể increment counters by batch
- Atomic batch result reporting

### Decision 4: Include minimal result data

**What**: `results` array chỉ chứa `content_id` và basic analytics (sentiment, score), không include full analytics payload

**Why**:

- Giảm message size
- Full data đã được lưu vào database
- Collector chỉ cần counts và IDs để track progress

## Component Design

### Publisher Class

```python
# infrastructure/messaging/publisher.py

class RabbitMQPublisher:
    """Publisher for sending analyze results to Collector."""

    def __init__(self, channel: AbstractRobustChannel):
        self.channel = channel
        self.exchange: Optional[AbstractExchange] = None

    async def setup(self, exchange_name: str) -> None:
        """Declare exchange for publishing."""
        self.exchange = await self.channel.declare_exchange(
            exchange_name,
            ExchangeType.TOPIC,
            durable=True,
        )

    async def publish_analyze_result(
        self,
        message: AnalyzeResultMessage,
        routing_key: str = "analyze.result",
    ) -> None:
        """Publish analyze result to Collector."""
        body = json.dumps(asdict(message)).encode()
        await self.exchange.publish(
            Message(body, delivery_mode=DeliveryMode.PERSISTENT),
            routing_key=routing_key,
        )
```

### Integration with Consumer

```python
# internal/consumers/main.py

async def process_event_format(envelope, db, publisher) -> dict:
    # ... existing processing logic ...

    # Build result message
    result_msg = AnalyzeResultMessage(
        success=error_count < len(batch_items),
        payload=AnalyzeResultPayload(
            project_id=project_id,
            job_id=job_id,
            task_type="analyze_result",
            batch_size=len(batch_items),
            success_count=success_count,
            error_count=error_count,
            results=build_result_items(processed_items),
            errors=build_error_items(error_items),
        )
    )

    # Publish to Collector
    await publisher.publish_analyze_result(result_msg)

    return {...}
```

## Configuration

```python
# core/config.py additions

# Result Publishing Settings
publish_exchange: str = "results.inbound"
publish_routing_key: str = "analyze.result"
publish_enabled: bool = True  # Feature flag for gradual rollout
```

## Error Handling

### MinIO Fetch Error

Khi không thể fetch batch từ MinIO, vẫn publish error result:

```python
if minio_fetch_error:
    error_msg = AnalyzeResultMessage(
        success=False,
        payload=AnalyzeResultPayload(
            project_id=project_id,
            job_id=job_id,
            task_type="analyze_result",
            batch_size=expected_item_count,
            success_count=0,
            error_count=expected_item_count,
            results=[],
            errors=[AnalyzeError(content_id="batch", error=str(error))],
        )
    )
    await publisher.publish_analyze_result(error_msg)
```

### Publish Failure

Nếu publish fails, log error nhưng không retry (message sẽ bị mất). Collector sẽ detect missing results qua timeout mechanism.

## Risks / Trade-offs

| Risk                            | Mitigation                                          |
| ------------------------------- | --------------------------------------------------- |
| Message loss on publish failure | Log error, rely on Collector timeout detection      |
| Exchange not exists             | Declare exchange on startup (idempotent)            |
| Schema drift                    | Version message format, add backward compatibility  |
| Large message size              | Limit results array, exclude full analytics payload |

## Migration Plan

1. **Phase 1**: Deploy publisher code với `publish_enabled=False`
2. **Phase 2**: Enable publishing in staging, verify Collector receives messages
3. **Phase 3**: Enable in production với monitoring
4. **Rollback**: Set `publish_enabled=False` to disable without code change

## Open Questions

- [ ] Should we implement retry logic for failed publishes?
- [ ] Should we include full analytics payload in results array?
- [ ] Should we add message TTL for stale results?
