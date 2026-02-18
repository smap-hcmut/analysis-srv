# Phase 5: AI Modules Integration Plan

**Ngày tạo:** 19/02/2026  
**Mục tiêu:** Integrate 3 AI modules (Intent Classification, Keyword Extraction, Sentiment Analysis) vào analytics pipeline  
**File cần sửa:** `internal/analytics/usecase/process.py`

---

## 1. TỔNG QUAN

Hiện tại trong `_run_pipeline()` có 3 stages đang có TODO comments:

- **Stage 2:** Intent Classification ⚠️
- **Stage 3:** Keyword Extraction ⚠️
- **Stage 4:** Sentiment Analysis ⚠️

Các modules này đã được implement đầy đủ và sẵn sàng sử dụng, chỉ cần integrate vào pipeline.

---

## 2. CHI TIẾT IMPLEMENTATION

### 2.1 Stage 2: Intent Classification Integration

**Vị trí:** `internal/analytics/usecase/process.py` - dòng 272-276

**Logic:**

1. Gọi intent classifier với `full_text` (đã được preprocess)
2. Map output vào `result.primary_intent` và `result.intent_confidence`
3. Nếu `should_skip == True` (SPAM/SEEDING), set status và return early

**Code:**

```python
# === STAGE 2: INTENT CLASSIFICATION ===

if self.config.enable_intent_classification and self.intent_classifier:
    try:
        from internal.intent_classification.type import Input as ICInput

        ic_input = ICInput(text=full_text)
        ic_output = self.intent_classifier.process(ic_input)

        # Update result
        result.primary_intent = ic_output.intent.name
        result.intent_confidence = ic_output.confidence

        # Skip if spam/seeding
        if ic_output.should_skip:
            result.processing_status = "success_skipped"
            result.risk_level = "LOW"
            # Early return - skip remaining stages
            return result

    except Exception as e:
        self.logger.error(f"internal.analytics.usecase.process: Intent classification failed: {e}")
        # Continue pipeline even if intent classification fails
```

**Lưu ý:**

- Import `Input` từ `internal.intent_classification.type` với alias `ICInput` để tránh conflict với `Input` của analytics
- Early return nếu `should_skip == True` để không waste resources cho các stages sau
- Error handling: log nhưng không fail pipeline

---

### 2.2 Stage 3: Keyword Extraction Integration

**Vị trí:** `internal/analytics/usecase/process.py` - dòng 278-282

**Logic:**

1. Gọi keyword extractor với `full_text`
2. Map keywords vào `result.keywords` (list of strings)
3. Lưu keywords với aspect info để dùng cho sentiment analysis (ABSA)

**Code:**

```python
# === STAGE 3: KEYWORD EXTRACTION ===

keywords_for_sentiment = []  # Store for Stage 4 (ABSA)

if self.config.enable_keyword_extraction and self.keyword_extractor:
    try:
        from internal.keyword_extraction.type import Input as KEInput

        ke_input = KEInput(text=full_text)
        ke_output = self.keyword_extractor.process(ke_input)

        # Update result - extract keyword strings
        result.keywords = [kw.keyword for kw in ke_output.keywords]

        # Store keywords with aspect info for sentiment analysis
        keywords_for_sentiment = ke_output.keywords

    except Exception as e:
        self.logger.error(f"internal.analytics.usecase.process: Keyword extraction failed: {e}")
        # Continue pipeline even if keyword extraction fails
```

**Lưu ý:**

- Import `Input` với alias `KEInput`
- Lưu `keywords_for_sentiment` để dùng ở Stage 4
- `ke_output.keywords` là `list[KeywordItem]` với fields: `keyword`, `aspect`, `score`, `source`

---

### 2.3 Stage 4: Sentiment Analysis Integration

**Vị trí:** `internal/analytics/usecase/process.py` - dòng 284-288

**Logic:**

1. Convert keywords từ Stage 3 sang `KeywordInput` format
2. Gọi sentiment analyzer với `full_text` và `keywords`
3. Map overall sentiment vào `result.overall_sentiment`, `result.overall_sentiment_score`, `result.overall_confidence`
4. Map aspect sentiments vào `result.aspects_breakdown` (JSONB structure)

**Code:**

```python
# === STAGE 4: SENTIMENT ANALYSIS ===

if self.config.enable_sentiment_analysis and self.sentiment_analyzer:
    try:
        from internal.sentiment_analysis.type import Input as SAInput, KeywordInput

        # Prepare keywords for ABSA (convert KeywordItem → KeywordInput)
        keyword_inputs = [
            KeywordInput(
                keyword=kw.keyword,
                aspect=kw.aspect,  # Already string from KeywordItem
                position=None,  # Not available from keyword extraction
                score=kw.score,
                source=kw.source,
            )
            for kw in keywords_for_sentiment
        ]

        sa_input = SAInput(text=full_text, keywords=keyword_inputs)
        sa_output = self.sentiment_analyzer.process(sa_input)

        # Update result - Overall sentiment
        result.overall_sentiment = sa_output.overall.label
        result.overall_sentiment_score = sa_output.overall.score
        result.overall_confidence = sa_output.overall.confidence

        # Store probabilities if available
        if sa_output.overall.probabilities:
            result.sentiment_probabilities = sa_output.overall.probabilities

        # Update result - Aspects breakdown
        aspects_list = []
        for aspect_name, aspect_sentiment in sa_output.aspects.items():
            aspects_list.append({
                "aspect": aspect_name,
                "polarity": aspect_sentiment.label,
                "confidence": aspect_sentiment.confidence,
                "score": aspect_sentiment.score,
                "evidence": ", ".join(aspect_sentiment.keywords[:3]) if aspect_sentiment.keywords else "",
                "mentions": aspect_sentiment.mentions,
                "rating": aspect_sentiment.rating,
            })

        if aspects_list:
            result.aspects_breakdown = {"aspects": aspects_list}

    except Exception as e:
        self.logger.error(f"internal.analytics.usecase.process: Sentiment analysis failed: {e}")
        # Continue pipeline even if sentiment analysis fails
```

**Lưu ý:**

- Import `Input` và `KeywordInput` từ `internal.sentiment_analysis.type`
- Convert `KeywordItem` → `KeywordInput` để match interface của sentiment analyzer
- Format `aspects_breakdown` theo structure JSONB để match với DB schema
- `aspect_sentiment.keywords` là `list[str]` (keyword strings), dùng làm evidence

---

## 3. DEPENDENCIES & FLOW

### 3.1 Stage Dependencies

```
Stage 1: Text Preprocessing
  ↓ (full_text, is_spam)

Stage 2: Intent Classification
  ↓ (primary_intent, should_skip?)
  → Early return if should_skip

Stage 3: Keyword Extraction
  ↓ (keywords list, keywords_for_sentiment)

Stage 4: Sentiment Analysis
  ↓ (overall_sentiment, aspects_breakdown)

Stage 5: Impact Calculation
  ↓ (impact_score, risk_level, etc.)
```

### 3.2 Data Flow

1. **Text Preprocessing** → `full_text` (cleaned text)
2. **Intent Classification** → `primary_intent`, `intent_confidence`, `should_skip`
   - Nếu `should_skip == True` → return early
3. **Keyword Extraction** → `keywords` (list[str]), `keywords_for_sentiment` (list[KeywordItem])
4. **Sentiment Analysis** → `overall_sentiment`, `overall_sentiment_score`, `overall_confidence`, `aspects_breakdown`
   - Sử dụng `keywords_for_sentiment` để làm ABSA
5. **Impact Calculation** → sử dụng sentiment từ Stage 4 để tính risk

---

## 4. ERROR HANDLING STRATEGY

### 4.1 Non-Fatal Errors

Tất cả 3 stages đều có error handling với strategy:

- **Log error** nhưng **không fail pipeline**
- **Continue** với default values hoặc empty data
- Pipeline vẫn chạy các stages sau

### 4.2 Default Values

Nếu stage fail, sử dụng defaults:

- **Intent Classification:** `primary_intent = "DISCUSSION"`, `intent_confidence = 0.0`
- **Keyword Extraction:** `keywords = []`
- **Sentiment Analysis:** `overall_sentiment = "NEUTRAL"`, `overall_sentiment_score = 0.0`, `aspects_breakdown = {}`

### 4.3 Early Return Logic

Chỉ **Stage 2 (Intent Classification)** có early return:

- Nếu `should_skip == True` (SPAM/SEEDING)
- Set `processing_status = "success_skipped"`
- Set `risk_level = "LOW"`
- Return ngay, không chạy stages sau

---

## 5. TESTING CHECKLIST

### 5.1 Unit Tests (Manual Verification)

- [ ] Intent classification với text có SPAM patterns → `should_skip == True`
- [ ] Intent classification với text có SEEDING patterns → `should_skip == True`
- [ ] Intent classification với normal text → `should_skip == False`
- [ ] Keyword extraction trả về keywords với aspect info
- [ ] Sentiment analysis với keywords → có aspect sentiments trong `aspects_breakdown`
- [ ] Sentiment analysis không có keywords → chỉ có overall sentiment

### 5.2 Integration Tests

- [ ] End-to-end: UAP input → DB record có đầy đủ fields
- [ ] Verify `primary_intent` trong DB
- [ ] Verify `keywords` trong DB (TEXT[])
- [ ] Verify `overall_sentiment`, `overall_sentiment_score`, `overall_confidence` trong DB
- [ ] Verify `aspects_breakdown` trong DB (JSONB structure)
- [ ] Verify early return khi `should_skip == True` (không có sentiment/keywords trong DB)

### 5.3 Edge Cases

- [ ] Empty text → các stages handle gracefully
- [ ] Intent classification exception → pipeline continue
- [ ] Keyword extraction exception → pipeline continue
- [ ] Sentiment analysis exception → pipeline continue
- [ ] Missing keywords → sentiment analysis chỉ làm overall (không có ABSA)

---

## 6. VERIFICATION STEPS

### 6.1 Code Review Checklist

- [ ] Imports đúng modules và types
- [ ] Error handling đầy đủ cho mỗi stage
- [ ] Early return logic đúng (chỉ Stage 2)
- [ ] Data mapping đúng format (Intent name, keywords list, aspects JSONB)
- [ ] Logging messages rõ ràng

### 6.2 Runtime Verification

1. **Start service** với config enable các stages
2. **Send UAP message** qua Kafka
3. **Check logs** để verify:
   - Intent classification chạy và log output
   - Keyword extraction chạy và log output
   - Sentiment analysis chạy và log output
4. **Check DB record** để verify:
   - `primary_intent` có giá trị
   - `keywords` có list keywords
   - `overall_sentiment` có giá trị
   - `aspects_breakdown` có structure đúng
5. **Check early return** với SPAM text → verify không có sentiment/keywords

---

## 7. ESTIMATED EFFORT

- **Coding:** 1-2 hours
- **Testing:** 1-2 hours
- **Code review:** 30 minutes
- **Total:** ~3-4 hours

---

## 8. RISKS & MITIGATIONS

| Risk                         | Impact | Mitigation                                           |
| :--------------------------- | :----- | :--------------------------------------------------- |
| Import conflicts             | LOW    | Use aliases (ICInput, KEInput, SAInput)              |
| Type mismatch                | MEDIUM | Verify type conversions (KeywordItem → KeywordInput) |
| Early return logic sai       | HIGH   | Test với SPAM/SEEDING text, verify DB                |
| Aspects breakdown format sai | MEDIUM | Verify với DB schema, check JSONB structure          |
| Performance impact           | LOW    | Error handling non-blocking, continue on failure     |

---

## 9. IMPLEMENTATION ORDER

1. ✅ **Stage 2: Intent Classification** (đơn giản nhất, có early return)
2. ✅ **Stage 3: Keyword Extraction** (cần để feed Stage 4)
3. ✅ **Stage 4: Sentiment Analysis** (phụ thuộc Stage 3)

---

## 10. POST-IMPLEMENTATION

Sau khi implement xong:

1. Remove TODO comments
2. Update `documents/analysis.md` - mark Phase 5 as COMPLETED
3. Test với real UAP messages
4. Monitor logs và DB records
5. Verify enriched output có đầy đủ data

---

**END OF PLAN**
