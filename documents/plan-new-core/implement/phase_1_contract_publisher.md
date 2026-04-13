# Phase 1 — Contract Publisher

> **Priority:** CRITICAL PATH — làm trước tất cả mọi thứ
> **Module:** `internal/contract_publisher/`
> **Gate:** knowledge-srv nhận và index được cả 3 topics không lỗi schema
> **Ref contract:** `contract.md v1.2`

## Mục tiêu

Implement `internal/contract_publisher/` để publish đúng 3 Kafka topics theo contract.
Dùng dữ liệu từ NLP pipeline **hiện có** (không cần Phase 2–4 xong trước).
Đây là bước đầu tiên để close gap giữa analysis-srv và knowledge-srv.

## Folder structure

```
internal/contract_publisher/
├── interface.py          # IContractPublisher (Protocol)
├── type.py               # PublishInput, PublishOutput, RunContext
├── constant.py           # TOPIC_BATCH_COMPLETED, TOPIC_INSIGHTS_PUBLISHED, TOPIC_REPORT_DIGEST
├── errors.py             # ContractPublishError, InvalidPayloadError
└── usecase/
    ├── new.py            # factory
    ├── usecase.py        # ContractPublisherUseCase — thin wrapper
    ├── publish_batch.py  # build_batch_completed_payload()
    ├── publish_insights.py  # build_insights_published_payloads()
    ├── publish_digest.py    # build_report_digest_payload()
    ├── publish_order.py     # publish_in_required_order() — enforces ordering
    └── helpers.py           # shared helpers (enum normalization, field mapping)

internal/runtime/
├── interface.py
├── type.py
├── constant.py
└── usecase/
    ├── new.py
    ├── run_id.py          # default_run_id() → "run-YYYYMMDDTHHMMSSz"
    └── enum_registry.py   # normalize_enum_value(), build_enum_registry()
```

## `RunContext` — dùng xuyên suốt

```python
# internal/contract_publisher/type.py
@dataclass
class RunContext:
    run_id: str          # "run-20260409T143022Z"
    project_id: str      # "proj_cleanser_01"
    campaign_id: str     # "camp_q1_2026"
    platform: str        # "tiktok" (lowercase per contract Layer 1)
    domain_overlay: str  # "domain-facial-cleanser-vn"
    analysis_window_start: str  # RFC3339 UTC
    analysis_window_end: str    # RFC3339 UTC
```

## `constant.py`

```python
TOPIC_BATCH_COMPLETED    = "analytics.batch.completed"
TOPIC_INSIGHTS_PUBLISHED = "analytics.insights.published"
TOPIC_REPORT_DIGEST      = "analytics.report.digest"

# Đây là 3 topics được consume bởi knowledge-srv.
# KHÔNG dùng "smap.analytics.output" — legacy, không có consumer.
```

## `publish_batch.py` — `build_batch_completed_payload()`

**Input:** List `InsightMessage` (từ pipeline hiện tại) + `RunContext`

**Output:** JSON object cho Kafka message

```python
def build_batch_completed_payload(
    documents: list[InsightMessage],
    ctx: RunContext,
) -> dict:
    return {
        "project_id": ctx.project_id,
        "campaign_id": ctx.campaign_id,
        "documents": [_map_document(doc) for doc in documents if _should_include(doc)],
    }

def _map_document(doc: InsightMessage) -> dict:
    result = {
        "identity": {
            "uap_id":          doc.identity.doc_id,          # → uap_id
            "uap_type":        doc.identity.doc_type,         # post/comment/reply (lowercase)
            "uap_media_type":  doc.identity.media_type or "text",  # default "text" nếu missing
            "platform":        _normalize_platform(doc.identity.source_type),  # TIKTOK uppercase
            "published_at":    doc.identity.published_at,
        },
        "content": {
            "clean_text": doc.content.clean_text or doc.content.text,
            "summary":    doc.content.summary or _truncate_summary(doc.content.clean_text),
        },
        "nlp": {
            "sentiment": {
                "label": _normalize_sentiment_label(doc.nlp.sentiment.label),  # uppercase
                "score":  _normalize_sentiment_score(doc.nlp.sentiment.label, doc.nlp.sentiment.score),
            },
            "aspects":  [_map_aspect(a) for a in doc.nlp.aspects],
            "entities": [_map_entity(e) for e in doc.nlp.entities],
        },
        "business": {
            "impact": {
                "engagement": {
                    "likes":    doc.business.impact.engagement.like_count,    # rename
                    "comments": doc.business.impact.engagement.comment_count, # rename
                    "shares":   doc.business.impact.engagement.share_count,   # rename
                    "views":    doc.business.impact.engagement.view_count,    # rename
                },
                "impact_score": doc.business.impact.impact_score,
                "priority":     doc.business.impact.priority,
            }
        },
        "rag": bool(doc.rag.index.should_index),  # flatten object → bool
    }
    # Optional fields [v1.2] — chỉ add nếu có data
    if doc.nlp.issues:
        result["nlp"]["issues"] = [_map_issue(i) for i in doc.nlp.issues]
    if doc.nlp.stance:
        result["nlp"]["stance"] = doc.nlp.stance
    if doc.nlp.intent:
        result["nlp"]["intent"] = doc.nlp.intent
    if doc.business.influence_tier:
        result["business"]["influence_tier"] = doc.business.influence_tier
    return result
```

**Critical helpers:**

```python
def _normalize_platform(source_type: str) -> str:
    """Contract Layer 3 expects UPPERCASE: "TIKTOK", "FACEBOOK", etc."""
    return source_type.upper() if source_type else "OTHER"

def _normalize_sentiment_score(label: str, score: float) -> float:
    """Contract range: -1.0 to +1.0. Current model: 0.0 to 1.0.
    NEGATIVE sentiment → negate score."""
    if label == "NEGATIVE" and score > 0:
        return -score
    return score

def _normalize_sentiment_label(label: str) -> str:
    return label.upper()  # Đảm bảo POSITIVE/NEGATIVE/NEUTRAL/MIXED

def _truncate_summary(text: str, max_chars: int = 120) -> str:
    """Fallback summary từ clean_text nếu summary field empty."""
    if not text:
        return ""
    return text[:max_chars].rstrip() + ("…" if len(text) > max_chars else "")

def _should_include(doc: InsightMessage) -> bool:
    """Gate: chỉ include documents có clean_text và uap_id."""
    return bool(doc.identity.doc_id and (doc.content.clean_text or doc.content.text))
```

## `publish_insights.py` — `build_insights_published_payloads()`

**Input:** `InsightCard[]` từ core-analysis + `RunContext`

**Output:** List of Kafka message dicts (1 per card)

```python
def build_insights_published_payloads(
    cards: list[InsightCard],
    ctx: RunContext,
) -> list[dict]:
    return [_map_card(card, ctx) for card in cards if card.confidence > 0]

def _map_card(card: InsightCard, ctx: RunContext) -> dict:
    window_start, window_end = _parse_time_window(card.time_window)
    result = {
        "project_id":             ctx.project_id,
        "campaign_id":            ctx.campaign_id,
        "run_id":                 ctx.run_id,
        "insight_type":           card.insight_type,
        "title":                  card.title,
        "summary":                card.summary,
        "confidence":             card.confidence,
        "analysis_window_start":  window_start or ctx.analysis_window_start,
        "analysis_window_end":    window_end   or ctx.analysis_window_end,
        "supporting_metrics":     card.supporting_metrics,
        "evidence_references":    card.evidence_references,
        "should_index":           bool(card.title and card.summary and card.confidence >= 0.3),
    }
    # Optional [v1.2]
    sm = card.supporting_metrics
    if sm.get("reportability_score") is not None:
        result["reportability_score"] = sm["reportability_score"]
    if sm.get("usefulness_score") is not None:
        result["usefulness_score"] = sm["usefulness_score"]
    return result

def _parse_time_window(time_window: str) -> tuple[str | None, str | None]:
    """Parse "2026-01-01T00:00:00 to 2026-03-31T23:59:59" → (start, end)"""
    if not time_window or " to " not in time_window:
        return None, None
    parts = time_window.split(" to ", 1)
    start = parts[0].strip().replace(" ", "T") + "Z" if "Z" not in parts[0] else parts[0].strip()
    end   = parts[1].strip().replace(" ", "T") + "Z" if "Z" not in parts[1] else parts[1].strip()
    return start, end
```

## `publish_digest.py` — `build_report_digest_payload()`

**Input:** `BIReportBundle` + `RunContext` + `total_mentions: int`

```python
def build_report_digest_payload(
    bundle: BIReportBundle,
    ctx: RunContext,
    total_mentions: int,
) -> dict:
    return {
        "project_id":             ctx.project_id,
        "campaign_id":            ctx.campaign_id,
        "run_id":                 ctx.run_id,
        "analysis_window_start":  ctx.analysis_window_start,
        "analysis_window_end":    ctx.analysis_window_end,
        "domain_overlay":         ctx.domain_overlay,
        "platform":               ctx.platform,  # lowercase per contract Layer 1
        "total_mentions":         total_mentions,
        "top_entities":           [_map_entity_row(e) for e in bundle.sov_report.entities[:10]],
        "top_topics":             [_map_topic_row(t) for t in bundle.buzz_report.topic_buzz[:10]],
        "top_issues":             [_map_issue_row(i) for i in bundle.top_issues_report.top_issues[:10]],
        "should_index":           True,
    }

def _map_entity_row(row) -> dict:   # SOVRow
    return {
        "canonical_entity_id": row.canonical_entity_id,
        "entity_name":         row.entity_name,
        "entity_type":         row.entity_type,
        "mention_count":       row.mention_count,
        "mention_share":       row.mention_share,
    }

def _map_topic_row(row) -> dict:   # BuzzTopicRow
    result = {
        "topic_key":     row.reporting_topic_key or row.reporting_topic_label.lower().replace(" ", "_"),
        "topic_label":   row.reporting_topic_label,
        "mention_count": row.mention_count,
        "mention_share": row.mention_share,
    }
    # Conditionally add optional fields
    if row.buzz_score_proxy is not None:
        result["buzz_score_proxy"] = row.buzz_score_proxy
    if row.quality_score is not None:
        result["quality_score"] = row.quality_score
    # [v1.2] optional
    if row.effective_mention_count:
        result["effective_mention_count"] = row.effective_mention_count
    if row.growth_ratio_proxy is not None:
        result["growth_ratio_proxy"] = row.growth_ratio_proxy
    if row.salient_terms:
        result["salient_terms"] = row.salient_terms[:10]
    return result

def _map_issue_row(row) -> dict:   # TopIssueRow
    result = {
        "issue_category":       row.issue_category,
        "mention_count":        row.mention_count,
        "issue_pressure_proxy": row.issue_pressure_proxy,
    }
    if row.severity_mix:
        result["severity_mix"] = row.severity_mix
    return result
```

## `publish_order.py` — `publish_in_required_order()`

```python
def publish_in_required_order(
    batch_payload: dict,
    insight_payloads: list[dict],
    digest_payload: dict,
    kafka_producer,       # pkg/kafka producer interface
    logger,
) -> None:
    """
    Contract mandate: batch → insights × N → digest (TRONG ĐÓ THỨ TỰ NÀY).
    Knowledge-srv dùng digest làm trigger export → phải publish cuối.
    """
    # 1. Layer 3 — batch (1 message, có thể lớn ~4MB)
    kafka_producer.publish(
        topic=TOPIC_BATCH_COMPLETED,
        key=batch_payload["project_id"],
        value=batch_payload,
    )
    logger.info("[ContractPublisher] batch.completed published",
                extra={"doc_count": len(batch_payload["documents"])})

    # 2. Layer 2 — insight cards (5–15 messages)
    for card in insight_payloads:
        kafka_producer.publish(
            topic=TOPIC_INSIGHTS_PUBLISHED,
            key=card["run_id"],
            value=card,
        )
    logger.info("[ContractPublisher] insights.published published",
                extra={"count": len(insight_payloads)})

    # 3. Layer 1 — digest (PHẢI cuối cùng — trigger NotebookLM export)
    kafka_producer.publish(
        topic=TOPIC_REPORT_DIGEST,
        key=digest_payload["run_id"],
        value=digest_payload,
    )
    logger.info("[ContractPublisher] report.digest published — run complete",
                extra={"run_id": digest_payload["run_id"]})
```

## Schema gap checklist

Trước khi submit Phase 1 gate, verify từng gap:

| Gap | Fix |
|---|---|
| `rag` field: object → bool | `bool(doc.rag.index.should_index)` ✅ |
| Engagement field names (`like_count` → `likes`) | Mapped trong `_map_document()` ✅ |
| `sentiment.score` range: 0–1 → -1 to +1 | `_normalize_sentiment_score()` ✅ |
| `content.summary` empty string | `_truncate_summary()` fallback ✅ |
| `nlp.entities[]` always empty | Phase 3 fix — tạm chấp nhận empty array ⚠️ |
| `platform` case trong Layer 3 vs Layer 1 | Layer 3: UPPERCASE, Layer 1: lowercase ✅ |
| `insight.time_window` string → 2 fields | `_parse_time_window()` ✅ |
| `uap_media_type` không có trong InsightMessage | Default "text", fix properly trong Phase 3 ⚠️ |

## Deprecate `smap.analytics.output`

Sau khi Phase 1 pass gate, xóa hoặc comment out:

```
internal/analytics/delivery/kafka/producer/constant.py
    TOPIC_ANALYTICS_OUTPUT = "smap.analytics.output"  # ← DELETE
```

Disable producer trong `internal/analytics/delivery/kafka/producer/publisher.py`.
