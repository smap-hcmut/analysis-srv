# Phase 5: Code Plan — Data Mapping Implementation

**Ref:** `documents/master-proposal.md` (Phase 5), `refactor_plan/04_data_mapping.md`
**Convention:** `documents/convention/`
**Depends on:** Phase 1 + Phase 2 + Phase 3 + Phase 4 (done)

---

## 0. SCOPE

Phase 5 là phase CUỐI CÙNG để hoàn thiện data flow từ UAP Input → Enriched Output. Sau Phase 5, pipeline sẽ:

1. **Nhận UAP Input** (Phase 1) → Parse và validate
2. **Chạy AI pipeline** (Phase 4) → Tính toán metrics
3. **Lưu DB** (Phase 3) → Schema mới `analytics.post_analytics`
4. **Build Enriched Output** (Phase 2 + Phase 5) → Transform UAP + AI Result
5. **Publish Kafka** (Phase 2) → Batch array to Knowledge Service

**Phase 5 focus:** Implement chính xác logic mapping UAP → Enriched Output theo `04_data_mapping.md`.

**IN SCOPE:**
- Refactor pipeline Input type: `PostData` + `EventMetadata` → UAP-based
- Update `_enrich_post_data()` để dùng UAP fields
- Update `_run_pipeline()` để extract data từ UAP
- Update `_add_crawler_metadata()` để map UAP metadata
- Clean up legacy types: `PostData`, `EventMetadata`, `EnrichedPostData`
- Update presenters để map UAP → Pipeline Input

**OUT OF SCOPE:**
- Legacy cleanup (Phase 6)
- New AI models
- Performance optimization


---

## 1. FILE PLAN

### 1.1 Files sửa (MODIFY)

| #   | File                                                          | Thay đổi                                                                                      |
| --- | ------------------------------------------------------------- | --------------------------------------------------------------------------------------------- |
| 1   | `internal/analytics/type.py`                                  | Refactor `Input` type: remove legacy `PostData`/`EventMetadata`, use UAP-based fields         |
| 2   | `internal/analytics/usecase/usecase.py`                       | Update `_enrich_post_data()` → extract từ UAP, không dùng `EventMetadata`                     |
| 3   | `internal/analytics/usecase/usecase.py`                       | Update `_run_pipeline()` → extract text, metrics từ UAP blocks                                |
| 4   | `internal/analytics/usecase/usecase.py`                       | Update `_add_crawler_metadata()` → map UAP metadata vào `AnalyticsResult`                     |
| 5   | `internal/analytics/delivery/rabbitmq/consumer/presenters.py` | Update `to_pipeline_input()` → map UAP → new Input type                                       |
| 6   | `internal/analytics/delivery/rabbitmq/consumer/handler.py`    | Update handler để pass UAP fields vào pipeline                                                |
| 7   | `internal/analyzed_post/repository/postgre/helpers.py`        | Update `_build_uap_metadata()` → extract từ UAP-based AnalyticsResult                         |

### 1.2 Files xoá (DELETE) — Legacy Types

| #   | File                                  | Lý do                                                                |
| --- | ------------------------------------- | -------------------------------------------------------------------- |
| 8   | `internal/analytics/type.py`          | Xoá `PostData`, `EventMetadata`, `EnrichedPostData` dataclasses     |

### 1.3 Files KHÔNG đổi

- Phase 1/2/3/4 implementation — giữ nguyên
- AI modules (sentiment, keyword, intent, impact) — giữ nguyên
- Builder module — giữ nguyên (đã dùng UAP từ Phase 2)
- Repository layer — giữ nguyên


---

## 2. CHI TIẾT TỪNG FILE

### 2.1 `internal/analytics/type.py` — Refactor Input Type

**Xoá legacy types:**

```python
# === DELETE THESE CLASSES ===
# @dataclass
# class PostData:
#     """Raw post data from crawler (Atomic JSON format)."""
#     ...

# @dataclass
# class EventMetadata:
#     """Event metadata from RabbitMQ message."""
#     ...

# @dataclass
# class EnrichedPostData:
#     """Post data enriched with event metadata."""
#     ...
```

**Update `Input` dataclass:**

```python
@dataclass
class Input:
    """Input structure for analytics pipeline.
    
    Phase 5: UAP-based input, no legacy PostData/EventMetadata.
    """

    uap_record: UAPRecord  # Required: UAP record (Phase 1)
    project_id: str  # Required: from uap_record.ingest.project_id

    def __post_init__(self):
        if not self.uap_record:
            raise ValueError("uap_record is required")
        if not self.project_id:
            raise ValueError("project_id is required")
        
        # Validate UAP structure
        if not self.uap_record.ingest:
            raise ValueError("uap_record.ingest is required")
        if not self.uap_record.content:
            raise ValueError("uap_record.content is required")
```

**Lưu ý:** `Input` giờ chỉ cần `uap_record` + `project_id`. Tất cả data extract từ UAP blocks.


---

### 2.2 `internal/analytics/usecase/usecase.py` — Update `process()` Method

**Xoá `_enrich_post_data()` method** — không cần nữa vì data đã có trong UAP.

**Update `process()` signature:**

```python
async def process(self, input_data: Input) -> Output:
    """Process a single post through the analytics pipeline.
    
    Phase 5: Extract data directly from UAP, no enrichment step.
    
    Args:
        input_data: Input with UAP record
        
    Returns:
        Output with analytics result
        
    Raises:
        ValueError: If input is invalid
    """
    start_time = time.perf_counter()
    
    uap = input_data.uap_record
    project_id = input_data.project_id
    
    # Extract identifiers from UAP
    source_id = uap.ingest.source.source_id if uap.ingest.source else None
    doc_id = uap.content.doc_id if uap.content else None
    
    if self.logger:
        self.logger.info(
            f"[AnalyticsPipeline] Processing source_id={source_id}, doc_id={doc_id}"
        )
    
    try:
        # Run pipeline stages (extract data from UAP)
        result = self._run_pipeline(uap, project_id)
        
        # Calculate processing time
        processing_time_ms = int((time.perf_counter() - start_time) * 1000)
        result.processing_time_ms = processing_time_ms
        
        # Persist result (async)
        await self.analyzed_post_usecase.create(
            CreateAnalyzedPostInput(data=result.to_dict())
        )
        
        # Build enriched output + publish to Kafka
        await self._publish_enriched(input_data, result)
        
        if self.logger:
            self.logger.info(
                f"[AnalyticsPipeline] Completed source_id={source_id}, "
                f"status={result.processing_status}, elapsed_ms={processing_time_ms}"
            )
        
        return Output(
            result=result,
            processing_status=STATUS_SUCCESS,
        )
    
    except Exception as exc:
        if self.logger:
            self.logger.error(
                f"[AnalyticsPipeline] Error processing source_id={source_id}: {exc}"
            )
        
        # Return error output
        return Output(
            result=self._build_error_result(uap, project_id, str(exc)),
            processing_status=STATUS_ERROR,
            error_message=str(exc),
        )
```


---

### 2.3 `internal/analytics/usecase/usecase.py` — Update `_run_pipeline()` Method

**Replace signature và implementation:**

```python
def _run_pipeline(
    self, 
    uap: UAPRecord, 
    project_id: str
) -> AnalyticsResult:
    """Run the full analytics pipeline.
    
    Phase 5: Extract data directly from UAP blocks.
    
    Args:
        uap: UAP record with all input data
        project_id: Project ID
        
    Returns:
        AnalyticsResult with all calculated metrics
    """
    # === EXTRACT FROM UAP ===
    
    # Ingest block
    ingest = uap.ingest
    source_id = ingest.source.source_id if ingest.source else None
    source_type = ingest.source.source_type if ingest.source else PLATFORM_UNKNOWN
    platform = self._normalize_platform(source_type)
    
    # Content block
    content = uap.content
    doc_id = content.doc_id if content else None
    text = content.text if content else ""
    url = content.url if content else None
    published_at = content.published_at if content else None
    
    # Author
    author = content.author if content else None
    author_id = author.author_id if author else None
    author_name = author.display_name if author else None
    author_username = author.username if author else None
    author_followers = author.followers if author else 0
    author_is_verified = author.is_verified if author else False
    
    # Signals block
    signals = uap.signals
    engagement = signals.engagement if signals else None
    
    views = engagement.view_count if engagement else 0
    likes = engagement.like_count if engagement else 0
    comments = engagement.comment_count if engagement else 0
    shares = engagement.share_count if engagement else 0
    saves = engagement.save_count if engagement else 0
    
    # Batch info
    batch = ingest.batch if ingest else None
    received_at = batch.received_at if batch else None
    
    # === INITIALIZE RESULT ===
    
    import uuid
    
    result = AnalyticsResult(
        id=str(uuid.uuid4()),
        project_id=project_id,
        source_id=source_id,
        platform=platform,
        published_at=published_at,
        analyzed_at=datetime.now(timezone.utc),
        model_version=self.config.model_version,
    )
    
    # Add raw metrics
    result.view_count = views
    result.like_count = likes
    result.comment_count = comments
    result.share_count = shares
    result.save_count = saves
    result.follower_count = author_followers
    
    # Add UAP metadata
    self._add_uap_metadata(result, uap)
    
    # === STAGE 1: PREPROCESSING ===
    
    full_text = text
    
    if self.config.enable_preprocessing and self.preprocessor:
        try:
            # Prepare input for text preprocessing
            tp_input = TPInput(
                content=ContentInput(
                    text=text,
                    transcription="",  # UAP doesn't have transcription in content
                ),
                comments=[],  # UAP doesn't have comments in content
            )
            
            tp_output = self.preprocessor.process(tp_input)
            
            # Update result with spam detection info
            result.is_spam = tp_output.is_spam
            result.spam_reasons = tp_output.spam_reasons
            
            # Use clean text for subsequent stages
            full_text = tp_output.clean_text
            
            if result.is_spam:
                result.risk_level = "LOW"
                result.processing_status = "success_spam"
        
        except Exception as e:
            if self.logger:
                self.logger.error(f"[AnalyticsPipeline] Preprocessing failed: {e}")
    
    # === STAGE 2: INTENT CLASSIFICATION ===
    
    if self.config.enable_intent_classification and self.intent_classifier:
        # TODO: Implement intent classification
        pass
    
    # === STAGE 3: KEYWORD EXTRACTION ===
    
    if self.config.enable_keyword_extraction and self.keyword_extractor:
        # TODO: Implement keyword extraction
        pass
    
    # === STAGE 4: SENTIMENT ANALYSIS ===
    
    if self.config.enable_sentiment_analysis and self.sentiment_analyzer:
        # TODO: Implement sentiment analysis
        pass
    
    # === STAGE 5: IMPACT CALCULATION ===
    
    if self.config.enable_impact_calculation and self.impact_calculator:
        try:
            # Prepare input for impact calculation
            ic_input = ICInput(
                interaction=InteractionInput(
                    views=views,
                    likes=likes,
                    comments_count=comments,
                    shares=shares,
                    saves=saves,
                ),
                author=AuthorInput(
                    followers=author_followers,
                    is_verified=author_is_verified,
                ),
                sentiment=SentimentInput(
                    label=result.overall_sentiment,
                    score=result.overall_sentiment_score,
                ),
                platform=platform,
                text=full_text,
            )
            
            ic_output = self.impact_calculator.process(ic_input)
            
            # Update result with impact metrics
            result.impact_score = ic_output.impact_score
            result.risk_level = ic_output.risk_level
            result.is_viral = ic_output.is_viral
            result.is_kol = ic_output.is_kol
            result.engagement_score = ic_output.engagement_score
            result.virality_score = ic_output.virality_score
            result.influence_score = ic_output.influence_score
            result.risk_factors = ic_output.risk_factors
            
            # Map breakdown
            if ic_output.impact_breakdown:
                result.impact_breakdown = {
                    "engagement_score": ic_output.impact_breakdown.engagement_score,
                    "reach_score": ic_output.impact_breakdown.reach_score,
                    "platform_multiplier": ic_output.impact_breakdown.platform_multiplier,
                    "sentiment_amplifier": ic_output.impact_breakdown.sentiment_amplifier,
                    "raw_impact": ic_output.impact_breakdown.raw_impact,
                }
        
        except Exception as e:
            if self.logger:
                self.logger.error(
                    f"[AnalyticsPipeline] Impact calculation failed: {e}"
                )
    
    return result
```


---

### 2.4 `internal/analytics/usecase/usecase.py` — Add `_add_uap_metadata()` Method

**Thay thế `_add_crawler_metadata()` bằng `_add_uap_metadata()`:**

```python
def _add_uap_metadata(
    self,
    result: AnalyticsResult,
    uap: UAPRecord,
) -> None:
    """Add UAP metadata to result.
    
    Phase 5: Extract metadata from UAP blocks instead of legacy crawler metadata.
    
    Args:
        result: AnalyticsResult to update
        uap: UAP record
    """
    # Content fields
    if uap.content:
        result.content_text = uap.content.text
        result.permalink = uap.content.url
        
        # Author fields
        if uap.content.author:
            result.author_id = uap.content.author.author_id
            result.author_name = uap.content.author.display_name
            result.author_username = uap.content.author.username
            result.author_avatar_url = uap.content.author.avatar_url
            result.author_is_verified = uap.content.author.is_verified or False
        
        # Hashtags (if available in content)
        if hasattr(uap.content, 'hashtags'):
            result.hashtags = uap.content.hashtags
    
    # Batch context (from ingest)
    if uap.ingest and uap.ingest.batch:
        batch = uap.ingest.batch
        result.crawled_at = batch.received_at
        
        # Map batch_id to job_id for backward compatibility
        if hasattr(batch, 'batch_id'):
            result.job_id = batch.batch_id
    
    # Entity context (from ingest)
    if uap.ingest and uap.ingest.entity:
        entity = uap.ingest.entity
        result.brand_name = entity.brand
        # Map entity_name to keyword for backward compatibility
        result.keyword = entity.entity_name
    
    # Pipeline version
    platform = result.platform.lower() if result.platform else "unknown"
    result.pipeline_version = PIPELINE_VERSION_TEMPLATE.format(
        platform=platform, 
        version=PIPELINE_VERSION_NUMBER
    )
```

**Xoá method cũ:**

```python
# DELETE THIS METHOD
# def _add_crawler_metadata(self, result, meta, content, author):
#     ...
```


---

### 2.5 `internal/analytics/usecase/usecase.py` — Update `_build_error_result()` Method

**Update signature:**

```python
def _build_error_result(
    self,
    uap: UAPRecord,
    project_id: str,
    error_message: str,
) -> AnalyticsResult:
    """Build minimal result for error cases.
    
    Phase 5: Extract from UAP instead of PostData.
    
    Args:
        uap: UAP record
        project_id: Project ID
        error_message: Error message
        
    Returns:
        Minimal AnalyticsResult for error case
    """
    source_id = None
    platform = PLATFORM_UNKNOWN
    
    if uap.ingest and uap.ingest.source:
        source_id = uap.ingest.source.source_id
        platform = self._normalize_platform(uap.ingest.source.source_type)
    
    return AnalyticsResult(
        id=str(uuid.uuid4()),
        project_id=project_id,
        source_id=source_id,
        platform=platform,
        analyzed_at=datetime.now(timezone.utc),
        processing_status=STATUS_ERROR,
    )
```


---

### 2.6 `internal/analytics/delivery/rabbitmq/consumer/presenters.py` — Update Mapping

**Update `to_pipeline_input()` function:**

```python
def to_pipeline_input(
    uap_record: UAPRecord,
    project_id: str,
) -> Input:
    """Convert UAP record to pipeline Input.
    
    Phase 5: Direct mapping, no legacy PostData/EventMetadata.
    
    Args:
        uap_record: Parsed UAP record
        project_id: Project ID from ingest block
        
    Returns:
        Pipeline Input
        
    Raises:
        ValueError: If required fields missing
    """
    if not uap_record:
        raise ValueError("uap_record is required")
    
    if not project_id:
        raise ValueError("project_id is required")
    
    # Validate UAP structure
    if not uap_record.ingest:
        raise ValueError("uap_record.ingest is required")
    
    if not uap_record.content:
        raise ValueError("uap_record.content is required")
    
    # Create Input
    return Input(
        uap_record=uap_record,
        project_id=project_id,
    )
```

**Xoá legacy functions:**

```python
# DELETE THESE FUNCTIONS
# def parse_message(raw_message: dict) -> tuple[PostData, EventMetadata]:
#     ...
# 
# def parse_event_metadata(meta: dict) -> EventMetadata:
#     ...
# 
# def parse_post_payload(payload: dict) -> PostData:
#     ...
```


---

### 2.7 `internal/analytics/delivery/rabbitmq/consumer/handler.py` — Update Handler

**Update `handle()` method:**

```python
async def handle(self, message: IncomingMessage) -> None:
    """Handle incoming RabbitMQ message.
    
    Phase 5: Parse UAP, create Input, call pipeline.
    
    Args:
        message: RabbitMQ message
    """
    async with message.process():
        try:
            # Parse message body
            raw_body = message.body.decode("utf-8")
            raw_json = json.loads(raw_body)
            
            # Parse UAP (Phase 1)
            uap_record = self.uap_parser.parse(raw_json)
            
            # Extract project_id
            project_id = uap_record.ingest.project_id if uap_record.ingest else None
            if not project_id:
                self.logger.error("[Handler] Missing project_id in UAP")
                return
            
            # Convert to pipeline Input (Phase 5)
            pipeline_input = to_pipeline_input(
                uap_record=uap_record,
                project_id=project_id,
            )
            
            # Process through pipeline
            output = await self.pipeline.process(pipeline_input)
            
            if output.processing_status == STATUS_ERROR:
                self.logger.error(
                    f"[Handler] Pipeline error: {output.error_message}"
                )
            
        except UAPValidationError as e:
            self.logger.error(f"[Handler] UAP validation failed: {e}")
        
        except Exception as e:
            self.logger.error(f"[Handler] Unexpected error: {e}")
            raise
```

**Lưu ý:** Handler giờ chỉ cần parse UAP, extract project_id, và gọi pipeline. Không còn parse Event Envelope.


---

### 2.8 `internal/analyzed_post/repository/postgre/helpers.py` — Update UAP Metadata Builder

**Update `_build_uap_metadata()` function:**

```python
def _build_uap_metadata(data: Dict[str, Any]) -> Dict[str, Any]:
    """Build uap_metadata JSONB from AnalyticsResult fields.
    
    Phase 5: Extract from UAP-based AnalyticsResult.
    
    Args:
        data: AnalyticsResult.to_dict() output
        
    Returns:
        JSONB dict for uap_metadata column
    """
    metadata: Dict[str, Any] = {}
    
    # Author fields
    author_fields = {
        "author": "author_id",
        "author_display_name": "author_name",
        "author_username": "author_username",
        "author_followers": "follower_count",
        "author_is_verified": "author_is_verified",
    }
    for meta_key, data_key in author_fields.items():
        if val := data.get(data_key):
            metadata[meta_key] = val
    
    # Engagement
    engagement = {
        k: data[f]
        for k, f in [
            ("views", "view_count"),
            ("likes", "like_count"),
            ("comments", "comment_count"),
            ("shares", "share_count"),
            ("saves", "save_count"),
        ]
        if (val := data.get(f)) is not None
    }
    if engagement:
        metadata["engagement"] = engagement
    
    # Other fields
    for meta_key, data_key in [
        ("url", "permalink"),
        ("hashtags", "hashtags"),
    ]:
        if val := data.get(data_key):
            metadata[meta_key] = val
    
    # Phase 5: No more transcription, media_duration from legacy crawler
    # These fields are not in UAP content block
    
    return metadata
```

**Lưu ý:** Xoá references đến `content_transcription` và `media_duration` vì UAP không có fields này trong content block.


---

## 3. DATA FLOW (Phase 5)

```
RabbitMQ Message (UAP JSON)
    │
    ├── Handler.handle()
    │   ├── Parse UAP (UAPParser)
    │   ├── Extract project_id
    │   └── to_pipeline_input(uap_record, project_id) → Input
    │
    ├── Pipeline.process(Input)
    │   ├── Extract data from UAP blocks:
    │   │   ├── ingest.source → source_id, platform
    │   │   ├── content → text, author, url, published_at
    │   │   ├── signals.engagement → views, likes, comments, shares
    │   │   └── ingest.batch → received_at
    │   │
    │   ├── _run_pipeline(uap, project_id)
    │   │   ├── Stage 1: Preprocessing (spam detection)
    │   │   ├── Stage 2: Intent Classification
    │   │   ├── Stage 3: Keyword Extraction
    │   │   ├── Stage 4: Sentiment Analysis
    │   │   └── Stage 5: Impact Calculation
    │   │
    │   ├── _add_uap_metadata(result, uap)
    │   │   └── Map UAP fields → AnalyticsResult
    │   │
    │   ├── analyzed_post_usecase.create(result.to_dict())
    │   │   └── INSERT INTO analytics.post_analytics
    │   │
    │   └── _publish_enriched(input, result)
    │       └── ResultBuilder.build(uap_record, result) → Kafka
    │
    └── Return Output
```


---

## 4. FIELD MAPPING: UAP → AnalyticsResult

### 4.1 Direct Mapping (Identity & Metadata)

| UAP Input Field                     | AnalyticsResult Field | Logic                                    |
| ----------------------------------- | --------------------- | ---------------------------------------- |
| `ingest.project_id`                 | `project_id`          | Direct copy                              |
| `ingest.source.source_id`           | `source_id`           | Direct copy                              |
| `ingest.source.source_type`         | `platform`            | Uppercase (facebook → FACEBOOK)          |
| `content.doc_id`                    | —                     | Not stored (used for logging only)       |
| `content.text`                      | `content_text`        | Direct copy                              |
| `content.url`                       | `permalink`           | Direct copy                              |
| `content.published_at`              | `published_at`        | Direct copy                              |
| `ingest.batch.received_at`          | `crawled_at`          | Direct copy                              |
| `ingest.batch.batch_id`             | `job_id`              | Map for backward compatibility           |
| `ingest.entity.brand`               | `brand_name`          | Direct copy                              |
| `ingest.entity.entity_name`         | `keyword`             | Map for backward compatibility           |

### 4.2 Author Mapping

| UAP Input Field                     | AnalyticsResult Field | Logic                                    |
| ----------------------------------- | --------------------- | ---------------------------------------- |
| `content.author.author_id`          | `author_id`           | Direct copy                              |
| `content.author.display_name`       | `author_name`         | Direct copy                              |
| `content.author.username`           | `author_username`     | Direct copy                              |
| `content.author.avatar_url`         | `author_avatar_url`   | Direct copy                              |
| `content.author.followers`          | `follower_count`      | Direct copy                              |
| `content.author.is_verified`        | `author_is_verified`  | Direct copy (default False)              |

### 4.3 Engagement Mapping

| UAP Input Field                     | AnalyticsResult Field | Logic                                    |
| ----------------------------------- | --------------------- | ---------------------------------------- |
| `signals.engagement.view_count`     | `view_count`          | Direct copy (default 0)                  |
| `signals.engagement.like_count`     | `like_count`          | Direct copy (default 0)                  |
| `signals.engagement.comment_count`  | `comment_count`       | Direct copy (default 0)                  |
| `signals.engagement.share_count`    | `share_count`         | Direct copy (default 0)                  |
| `signals.engagement.save_count`     | `save_count`          | Direct copy (default 0)                  |

### 4.4 Calculated Fields (AI + Logic)

| AnalyticsResult Field               | Source                                   |
| ----------------------------------- | ---------------------------------------- |
| `overall_sentiment`                 | PhoBERT model inference (Stage 4)        |
| `overall_sentiment_score`           | PhoBERT model inference (Stage 4)        |
| `aspects_breakdown`                 | ABSA model extraction (Stage 4)          |
| `keywords`                          | YAKE + spaCy NER (Stage 3)               |
| `risk_level`                        | `evaluate_risk()` (Phase 4)              |
| `risk_score`                        | `evaluate_risk()` (Phase 4)              |
| `risk_factors`                      | `evaluate_risk()` (Phase 4)              |
| `engagement_score`                  | `calculate_engagement_score()` (Phase 4) |
| `virality_score`                    | `calculate_virality_score()` (Phase 4)   |
| `influence_score`                   | `calculate_influence_score()` (Phase 4)  |
| `is_spam`                           | `detect_spam()` (Phase 4)                |
| `spam_reasons`                      | `detect_spam()` (Phase 4)                |

### 4.5 Fields NOT in UAP (Legacy Crawler Only)

These fields are NOT available in UAP and will be removed or set to None:

| AnalyticsResult Field               | Status                                   |
| ----------------------------------- | ---------------------------------------- |
| `content_transcription`             | Not in UAP → None                        |
| `media_duration`                    | Not in UAP → None                        |
| `batch_index`                       | Not in UAP → None                        |
| `task_type`                         | Not in UAP → None                        |
| `keyword_source`                    | Not in UAP → None                        |


---

## 5. TESTING STRATEGY

### 5.1 Unit Tests

| Test                                  | File                                | Mô tả                                                      |
| ------------------------------------- | ----------------------------------- | ---------------------------------------------------------- |
| `test_input_validation`               | `tests/test_analytics_type.py`      | Test Input validation: uap_record required, project_id required |
| `test_to_pipeline_input`              | `tests/test_presenters.py`          | Test UAP → Input mapping                                   |
| `test_run_pipeline_uap_extraction`    | `tests/test_usecase.py`             | Test extract data từ UAP blocks                            |
| `test_add_uap_metadata`               | `tests/test_usecase.py`             | Test map UAP metadata vào AnalyticsResult                  |
| `test_build_error_result_uap`         | `tests/test_usecase.py`             | Test error result với UAP input                            |
| `test_build_uap_metadata_helper`      | `tests/test_helpers.py`             | Test _build_uap_metadata() với UAP-based data              |

### 5.2 Integration Tests

1. Send UAP message → verify AnalyticsResult fields mapped correctly
2. Verify `source_id` from UAP → DB `source_id` column
3. Verify `platform` from UAP → DB `platform` column (lowercase)
4. Verify author fields from UAP → DB `uap_metadata` JSONB
5. Verify engagement metrics from UAP → DB columns
6. Verify batch info from UAP → DB `crawled_at`, `job_id`
7. Verify entity context from UAP → DB `brand_name`, `keyword`

### 5.3 Edge Cases

| Case                                  | Expected Behavior                                  |
| ------------------------------------- | -------------------------------------------------- |
| UAP missing `ingest` block            | ValueError raised                                  |
| UAP missing `content` block           | ValueError raised                                  |
| UAP missing `signals` block           | Default values (0 for metrics)                     |
| UAP missing `author` block            | Default values (None for author fields)            |
| UAP missing `engagement` block        | Default values (0 for all metrics)                 |
| UAP missing `batch` block             | None for `crawled_at`, `job_id`                    |
| UAP missing `entity` block            | None for `brand_name`, `keyword`                   |
| Empty `text` field                    | Empty string, spam detection may flag              |


---

## 6. DEPENDENCY GRAPH

```
internal/analytics/type.py                       ← MODIFIED (remove legacy types, update Input)
    ↑
internal/analytics/delivery/rabbitmq/consumer/presenters.py  ← MODIFIED (update to_pipeline_input)
    ↑
internal/analytics/delivery/rabbitmq/consumer/handler.py     ← MODIFIED (use new Input)
    ↑
internal/analytics/usecase/usecase.py            ← MODIFIED (refactor pipeline methods)
    ├── process() — update signature
    ├── _run_pipeline() — extract from UAP
    ├── _add_uap_metadata() — replace _add_crawler_metadata
    └── _build_error_result() — update signature
    ↑
internal/analyzed_post/repository/postgre/helpers.py  ← MODIFIED (_build_uap_metadata)
```

**Thứ tự implement:**

1. `internal/analytics/type.py` — xoá legacy types, update Input
2. `internal/analytics/usecase/usecase.py` — update all methods
3. `internal/analytics/delivery/rabbitmq/consumer/presenters.py` — update mapping
4. `internal/analytics/delivery/rabbitmq/consumer/handler.py` — update handler
5. `internal/analyzed_post/repository/postgre/helpers.py` — update metadata builder
6. Write unit tests
7. Run integration tests
8. Verify end-to-end flow


---

## 7. CONVENTION ADHERENCE

### 7.1 Type Definitions

- ✅ `Input` type trong `type.py` (module root)
- ✅ Xoá legacy types: `PostData`, `EventMetadata`, `EnrichedPostData`
- ✅ Validation trong `__post_init__`
- ✅ Type hints đầy đủ

### 7.2 UseCase Layer

- ✅ Methods accept `Input` type (không phải raw dict)
- ✅ Extract data từ UAP blocks (không dùng legacy fields)
- ✅ Private methods prefix `_`
- ✅ Error handling với logging
- ✅ Framework-agnostic (không import aio_pika, sqlalchemy)

### 7.3 Delivery Layer

- ✅ Handler THIN — chỉ parse, validate, gọi usecase
- ✅ Presenters map UAP → Input
- ✅ Không có business logic trong delivery
- ✅ Error handling với logging

### 7.4 Code Style

- ✅ Docstrings: Google style
- ✅ Logging: Info level cho main flow, Debug cho details
- ✅ Type hints: Đầy đủ cho tất cả parameters và returns
- ✅ Constants: Dùng named constants thay vì magic strings


---

## 8. VERIFICATION CHECKLIST

### 8.1 Implementation

- [ ] Legacy types xoá: `PostData`, `EventMetadata`, `EnrichedPostData`
- [ ] `Input` type updated: chỉ cần `uap_record` + `project_id`
- [ ] `Input.__post_init__` validates UAP structure
- [ ] `process()` method updated: extract từ UAP
- [ ] `_enrich_post_data()` method xoá (không cần nữa)
- [ ] `_run_pipeline()` method updated: extract từ UAP blocks
- [ ] `_add_uap_metadata()` method added: replace `_add_crawler_metadata()`
- [ ] `_add_crawler_metadata()` method xoá
- [ ] `_build_error_result()` updated: accept UAP
- [ ] `to_pipeline_input()` updated: map UAP → Input
- [ ] Legacy presenter functions xoá: `parse_message()`, `parse_event_metadata()`, `parse_post_payload()`
- [ ] Handler updated: parse UAP, call pipeline
- [ ] `_build_uap_metadata()` updated: no transcription, media_duration

### 8.2 Testing

- [ ] Unit tests pass for new Input validation
- [ ] Unit tests pass for UAP extraction logic
- [ ] Unit tests pass for UAP metadata mapping
- [ ] Integration test: UAP message → DB record
- [ ] Integration test: source_id mapping
- [ ] Integration test: platform mapping (lowercase)
- [ ] Integration test: author fields in uap_metadata
- [ ] Integration test: engagement metrics
- [ ] Integration test: batch info mapping
- [ ] Integration test: entity context mapping

### 8.3 Data Quality

- [ ] No NULL values for required fields
- [ ] `source_id` populated from UAP
- [ ] `platform` lowercase (facebook, not FACEBOOK)
- [ ] `uap_metadata` JSONB valid
- [ ] Author fields in `uap_metadata`
- [ ] Engagement metrics correct
- [ ] Batch info mapped correctly
- [ ] Entity context mapped correctly

### 8.4 Backward Compatibility

- [ ] Phase 1/2/3/4 code still works
- [ ] Builder module still works (already uses UAP)
- [ ] Kafka publisher still works
- [ ] DB schema unchanged (Phase 3)
- [ ] No breaking changes to AI modules


---

## 9. RISKS & MITIGATIONS

| Risk                                      | Impact | Mitigation                                                    |
| ----------------------------------------- | ------ | ------------------------------------------------------------- |
| UAP missing required blocks               | HIGH   | Validate in `Input.__post_init__`, raise ValueError early     |
| UAP structure changes                     | HIGH   | Use Phase 1 UAPParser, centralized validation                |
| Legacy fields still referenced            | MEDIUM | Grep search for `PostData`, `EventMetadata`, `EnrichedPostData` |
| Missing fields in UAP vs legacy           | MEDIUM | Document fields NOT in UAP, set to None/default              |
| Performance impact from UAP parsing       | LOW    | UAP parsing already done in Phase 1, no extra overhead       |
| Breaking changes to AI modules            | LOW    | AI modules use `AnalyticsResult`, not Input type             |
| Integration test failures                 | MEDIUM | Run full integration tests before merge                      |

---

## 10. MIGRATION STRATEGY

### 10.1 Phased Rollout

1. **Week 1:** Implement Phase 5 changes
2. **Week 2:** Unit tests + Integration tests
3. **Week 3:** Deploy to staging, verify UAP messages
4. **Week 4:** Deploy to production, monitor errors
5. **Week 5:** Phase 6 (Legacy Cleanup) if stable

### 10.2 Rollback Plan

- Keep legacy code commented out (not deleted) for 1 week
- If issues found, uncomment legacy code and redeploy
- Fix issues in Phase 5 implementation
- Redeploy Phase 5 after fixes

### 10.3 Monitoring

- Monitor error rate in handler
- Monitor UAP validation errors
- Monitor missing fields warnings
- Monitor DB write success rate
- Monitor Kafka publish success rate

---

## 11. TIMELINE

| Task                                  | Estimate  |
| ------------------------------------- | --------- |
| Type refactoring                      | 0.5 day   |
| Pipeline methods refactoring          | 2 days    |
| Presenter + Handler updates           | 1 day     |
| Helpers updates                       | 0.5 day   |
| Unit Tests                            | 1 day     |
| Integration Tests                     | 1 day     |
| Bug fixes + Edge cases                | 1 day     |
| Documentation                         | 0.5 day   |
| **Total**                             | **7.5 days** |

---

**END OF PHASE 5 CODE PLAN**
