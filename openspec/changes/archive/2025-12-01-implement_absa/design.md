# Design: Aspect-Based Sentiment Analyzer (ABSA)

## Architectural Decisions

### Decision 1: Context Windowing vs Full-Text Analysis

**Problem**: PhoBERT ONNX is trained for overall sentiment, not aspect-specific. How to get aspect-level sentiment without retraining?

**Options**:
1. **Retrain model** with aspect-labeled data (expensive, time-consuming)
2. **Context Windowing** - Extract context around keywords and analyze separately (fast, leverages existing model)
3. **Multi-task learning** - Train model to predict both overall and aspect sentiment (complex, requires data)

**Decision**: **Context Windowing** (Option 2)

**Rationale**:
- ✅ No model retraining needed (uses existing PhoBERT ONNX)
- ✅ Fast implementation (algorithmic, not ML)
- ✅ Proven technique in ABSA literature
- ✅ Maintains <100ms performance target
- ⚠️ Trade-off: May miss long-range dependencies (acceptable for social media posts)

**Implementation**: Extract ±60 characters around keyword, snap to word boundaries.

---

### Decision 2: Sentiment Label Mapping

**Problem**: PhoBERT ONNX returns 5-class (1-5 stars: VERY_NEGATIVE to VERY_POSITIVE), but ABSA needs 3-class (POSITIVE/NEGATIVE/NEUTRAL) for simplicity.

**Options**:
1. **Direct mapping**: 1-2 → NEGATIVE, 3 → NEUTRAL, 4-5 → POSITIVE
2. **Score-based**: Convert to -1 to +1 score, use thresholds
3. **Keep 5-class**: Use all 5 classes in output

**Decision**: **Score-based with thresholds** (Option 2)

**Rationale**:
- ✅ More nuanced than direct mapping
- ✅ Allows fine-tuning thresholds based on business needs
- ✅ Consistent with master-proposal.md specification
- ✅ Enables weighted aggregation (scores are numeric)

**Implementation**:
- Map 5-class to score: 1→-1.0, 2→-0.5, 3→0.0, 4→0.5, 5→1.0
- Thresholds: POSITIVE if score > 0.25, NEGATIVE if score < -0.25, else NEUTRAL

---

### Decision 3: Context Window Size

**Problem**: What's the optimal window size for context extraction?

**Options**:
1. **Fixed size**: 50, 60, 80, 100 characters
2. **Sentence-based**: Extract full sentence containing keyword
3. **Adaptive**: Based on text length and keyword position

**Decision**: **Configurable fixed size with smart boundary snapping** (Option 1 enhanced)

**Rationale**:
- ✅ Simple and predictable
- ✅ Configurable via constants (easy to tune)
- ✅ Smart boundary snapping prevents word cutting
- ✅ 60 chars is good balance (captures context without noise)

**Implementation**: Default 60 characters, expand to nearest whitespace/punctuation.

---

### Decision 4: Aggregation Strategy

**Problem**: One aspect (e.g., PRICE) may appear multiple times. How to combine?

**Options**:
1. **Simple average**: Mean of all scores
2. **Weighted average**: Weight by confidence scores
3. **Majority vote**: Most common label wins
4. **Max/min**: Use strongest sentiment

**Decision**: **Weighted average by confidence** (Option 2)

**Rationale**:
- ✅ Respects model confidence (high confidence predictions matter more)
- ✅ Handles multiple mentions naturally
- ✅ Numeric scores enable mathematical aggregation
- ✅ Preserves nuance better than majority vote

**Formula**: `Score_final = Σ(Score_i × Confidence_i) / Σ(Confidence_i)`

---

### Decision 5: Integration with PhoBERT ONNX

**Problem**: How to use existing `PhoBERTONNX` class for both overall and aspect sentiment?

**Options**:
1. **Direct usage**: Call `PhoBERTONNX.predict()` for each context
2. **Wrapper adapter**: Create adapter that converts 5-class to 3-class
3. **Inheritance**: Extend `PhoBERTONNX` class

**Decision**: **Direct usage with helper methods** (Option 1)

**Rationale**:
- ✅ Minimal changes to existing code
- ✅ Clear separation of concerns
- ✅ Easy to test (mock PhoBERTONNX)
- ✅ Reuses proven infrastructure

**Implementation**: 
- `SentimentAnalyzer` takes `PhoBERTONNX` instance in constructor
- Helper method `_convert_to_absa_format()` maps 5-class to 3-class

---

### Decision 6: Error Handling

**Problem**: What if context extraction fails or PhoBERT prediction fails?

**Options**:
1. **Fail fast**: Raise exception, stop processing
2. **Graceful degradation**: Use overall sentiment as fallback
3. **Skip aspect**: Return overall only, log warning

**Decision**: **Graceful degradation with logging** (Option 2)

**Rationale**:
- ✅ System continues working even if aspect analysis fails
- ✅ Overall sentiment still available (better than nothing)
- ✅ Logging helps debug issues
- ✅ Production-ready (doesn't crash on edge cases)

**Implementation**:
- Try-catch around context extraction and prediction
- Fallback to overall sentiment if aspect analysis fails
- Log warnings for debugging

---

## Data Flow

```
Input:
  text: "Xe thiết kế đẹp nhưng giá quá đắt"
  keywords: [
    {keyword: "thiết kế", aspect: "DESIGN", position: 3},
    {keyword: "giá", aspect: "PRICE", position: 20}
  ]

Step 1: Overall Sentiment
  PhoBERTONNX.predict("Xe thiết kế đẹp nhưng giá quá đắt")
  → {rating: 3, sentiment: "NEUTRAL", confidence: 0.65}

Step 2: Aspect Sentiment (for each keyword)
  For "thiết kế" (DESIGN):
    Context: "Xe thiết kế đẹp nhưng" (±60 chars, snapped)
    PhoBERTONNX.predict("Xe thiết kế đẹp nhưng")
    → {rating: 5, sentiment: "VERY_POSITIVE", confidence: 0.92}
    → Convert: {score: 1.0, label: "POSITIVE", confidence: 0.92}
  
  For "giá" (PRICE):
    Context: "nhưng giá quá đắt" (±60 chars, snapped)
    PhoBERTONNX.predict("nhưng giá quá đắt")
    → {rating: 1, sentiment: "VERY_NEGATIVE", confidence: 0.88}
    → Convert: {score: -1.0, label: "NEGATIVE", confidence: 0.88}

Step 3: Aggregate (if multiple mentions of same aspect)
  (Not needed in this example - each aspect mentioned once)

Output:
{
  overall: {
    label: "NEUTRAL",
    score: 0.0,
    confidence: 0.65,
    probabilities: {...}
  },
  aspects: {
    DESIGN: {
      label: "POSITIVE",
      score: 1.0,
      confidence: 0.92,
      mentions: 1,
      keywords: ["thiết kế"]
    },
    PRICE: {
      label: "NEGATIVE",
      score: -1.0,
      confidence: 0.88,
      mentions: 1,
      keywords: ["giá"]
    }
  }
}
```

---

## Performance Considerations

### Optimization Strategies

1. **Lazy Loading**: Load PhoBERT model only when first used
2. **Context Caching**: Cache extracted contexts (if same text processed multiple times)
3. **Batch Processing**: Process multiple contexts in batch (if PhoBERT supports it)
4. **Early Exit**: Skip aspect analysis if no keywords provided

### Expected Performance

- **Overall sentiment**: ~50-80ms (PhoBERT ONNX inference)
- **Per-aspect sentiment**: ~50-80ms per keyword
- **Total for 3 keywords**: ~200-300ms (acceptable for <100ms target per aspect, overall <500ms per post)

**Note**: Performance target in master-proposal.md is <100ms per post, but this includes all modules. For Module 4 alone, <500ms is acceptable given multiple inferences.

---

## Testing Strategy

### Unit Tests
- Context extraction (various window sizes, edge cases)
- Score conversion (5-class to 3-class)
- Aggregation logic (single mention, multiple mentions)
- Error handling (empty text, missing keywords)

### Integration Tests
- End-to-end with real PhoBERT model
- Real Vietnamese text samples
- Multiple aspects in one text
- Conflict scenarios (positive and negative for same aspect)

### Performance Tests
- Benchmark inference time
- Memory usage
- Throughput (posts per second)

---

## Configuration

### Constants (in `core/config.py` or `infrastructure/ai/constants.py`)

```python
# Context Windowing
CONTEXT_WINDOW_SIZE = 60  # characters
CONTEXT_SNAP_TO_WORD = True  # expand to word boundaries

# Sentiment Thresholds
THRESHOLD_POSITIVE = 0.25  # score > 0.25 → POSITIVE
THRESHOLD_NEGATIVE = -0.25  # score < -0.25 → NEGATIVE

# Score Mapping (5-class to numeric)
SCORE_MAP = {
    1: -1.0,  # VERY_NEGATIVE
    2: -0.5,  # NEGATIVE
    3: 0.0,   # NEUTRAL
    4: 0.5,   # POSITIVE
    5: 1.0    # VERY_POSITIVE
}
```

---

## Future Enhancements (Out of Scope)

1. **Adaptive Window Size**: Adjust based on text length
2. **Sentence-Based Context**: Extract full sentences instead of character windows
3. **Cross-Aspect Dependencies**: Model relationships between aspects
4. **Confidence Calibration**: Improve confidence scores based on validation data
5. **Caching**: Cache sentiment results for duplicate texts

