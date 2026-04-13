# Business Requirements Inventory

Mục tiêu: liệt kê yêu cầu nghiệp vụ cần bảo toàn khi chuyển từ smap-analyse sang analysis-srv.

## BR-01: Ingest và chuẩn hóa UAP

- Nhận đủ post/comment/reply.
- Giữ quan hệ root/parent/depth.
- Chuẩn hóa text, language, timestamp UTC.

## BR-02: Enrichment NLP cốt lõi

- Sentiment: mention-level + target-level.
- Aspect opinion + issue signals.
- Entity extraction + canonicalization.
- Topic inference theo ontology.

## BR-03: Chất lượng dữ liệu

- Dedup exact + near.
- Spam scoring mention/author.
- Quality weight để phục vụ weighted metrics.

## BR-04: Metrics và BI

- SOV, buzz topics, emerging topics.
- Top issues + pressure proxy.
- Thread controversy proxy.
- Creator/source concentration.

## BR-05: Insights generation

- Sinh insight cards chuẩn hóa.
- Có evidence references (uap_id).
- Có confidence và supporting_metrics.

## BR-06: HIL/Review readiness

- Queue item confidence thấp hoặc ambiguous.
- Grouping và suppression theo quyết định trước đó.

## BR-07: Crisis detection

- Hỗ trợ keyword/volume/sentiment/influencer triggers.
- Resolve severity WARNING/CRITICAL.
- Publish event cho project khi trigger.

## BR-08: Contract compatibility

- Match strict contract cho knowledge:
  - analytics.batch.completed
  - analytics.insights.published
  - analytics.report.digest
- Publish order cố định: batch -> insights -> digest.

## BR-09: Observability và reliability

- Trace_id xuyên suốt inbound -> core -> outbound.
- Idempotency cho message/event.
- Outbox + retry/backoff + DLQ policy.

## BR-10: Run governance

- Run status lifecycle (queued/running/published/failed).
- Stage timing và run manifest để audit.
