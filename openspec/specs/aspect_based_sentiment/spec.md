# aspect_based_sentiment Specification

## Purpose
TBD - created by archiving change implement_absa. Update Purpose after archive.
## Requirements
### Requirement: Overall Sentiment Analysis

The Analytics Engine SHALL analyze overall sentiment of the entire text using PhoBERT ONNX model.

**Rationale**: Overall sentiment provides a high-level view of customer opinion, useful for quick assessment and filtering.

#### Scenario: Analyze overall sentiment for positive text

**Given** the text "Xe VinFast thiết kế rất đẹp, giá hợp lý, pin tốt"

**When** analyzing overall sentiment

**Then** the system SHALL:
- Call PhoBERT ONNX model with full text
- Return sentiment label (POSITIVE, NEGATIVE, or NEUTRAL)
- Return sentiment score (-1.0 to 1.0)
- Return confidence (0.0 to 1.0)
- Return probability distribution for all classes

#### Scenario: Handle empty text

**Given** the text is empty or whitespace only

**When** analyzing overall sentiment

**Then** the system SHALL return:
- Label: NEUTRAL
- Score: 0.0
- Confidence: 0.0

---

### Requirement: Context Windowing for Aspect Sentiment

The Analytics Engine SHALL extract context windows around keywords for aspect-level sentiment analysis.

**Rationale**: Analyzing full text for each aspect dilutes sentiment signals. Context windows focus the model on relevant portions, improving accuracy.

#### Scenario: Extract context window around keyword

**Given**:
- Text: "Xe chạy rất êm ái nhưng giá hơi cao so với phân khúc"
- Keyword: "giá" at position 20

**When** extracting context window with size 60 characters

**Then** the system SHALL:
- Extract ±60 characters around keyword position
- Snap boundaries to nearest whitespace or punctuation (avoid cutting words)
- Return context: "nhưng giá hơi cao so với phân khúc" (meaningful phrase)

#### Scenario: Handle keyword at text boundary

**Given**:
- Text: "Giá đắt quá"
- Keyword: "giá" at position 0

**When** extracting context window

**Then** the system SHALL:
- Start from position 0 (no negative start)
- Expand right to include full context
- Return context: "Giá đắt quá" (full text if shorter than window)

#### Scenario: Handle keyword not found

**Given**:
- Text: "Xe đẹp lắm"
- Keyword: "giá" (not in text)

**When** extracting context window

**Then** the system SHALL:
- Fallback to full text
- Log warning for debugging
- Continue processing (graceful degradation)

---

### Requirement: Aspect-Based Sentiment Analysis

The Analytics Engine SHALL determine sentiment for each business aspect by analyzing context windows around aspect keywords.

**Rationale**: Different aspects can have different sentiments in the same text (e.g., "Design is good but price is high"). Aspect-level analysis enables granular insights.

#### Scenario: Analyze sentiment for single aspect

**Given**:
- Text: "Xe thiết kế đẹp nhưng giá quá đắt"
- Keywords: [
    {keyword: "thiết kế", aspect: "DESIGN", position: 3},
    {keyword: "giá", aspect: "PRICE", position: 20}
  ]

**When** analyzing aspect sentiment

**Then** the system SHALL:
- For DESIGN aspect:
  - Extract context: "Xe thiết kế đẹp nhưng"
  - Call PhoBERT ONNX with context
  - Return: {label: "POSITIVE", score: >0.25, confidence: >0.7}
- For PRICE aspect:
  - Extract context: "nhưng giá quá đắt"
  - Call PhoBERT ONNX with context
  - Return: {label: "NEGATIVE", score: <-0.25, confidence: >0.7}

#### Scenario: Handle multiple mentions of same aspect

**Given**:
- Text: "Pin chán lắm, sạc 3 tiếng mới đầy, thất vọng về pin"
- Keywords: [
    {keyword: "pin", aspect: "PERFORMANCE", position: 0},
    {keyword: "sạc", aspect: "PERFORMANCE", position: 15},
    {keyword: "pin", aspect: "PERFORMANCE", position: 40}
  ]

**When** analyzing PERFORMANCE aspect sentiment

**Then** the system SHALL:
- Extract contexts for all 3 keywords
- Analyze each context separately
- Aggregate results using weighted average (by confidence)
- Return single sentiment for PERFORMANCE aspect:
  - Label: "NEGATIVE" (aggregated score < -0.25)
  - Mentions: 3
  - Keywords: ["pin", "sạc", "pin"]

#### Scenario: Handle aspect with no keywords

**Given**:
- Text: "Xe đẹp lắm"
- Keywords: [
    {keyword: "xe", aspect: "GENERAL", position: 0}
  ]

**When** analyzing aspect sentiment

**Then** the system SHALL:
- Skip aspects with no keywords (DESIGN, PERFORMANCE, PRICE, SERVICE)
- Only return sentiment for GENERAL aspect
- Return empty dict for missing aspects (or omit from output)

---

### Requirement: Sentiment Score Conversion

The Analytics Engine SHALL convert PhoBERT 5-class output (1-5 stars) to 3-class ABSA format (POSITIVE/NEGATIVE/NEUTRAL) with numeric scores.

**Rationale**: PhoBERT returns 5-class ratings, but ABSA needs simpler 3-class labels for business clarity. Numeric scores enable aggregation.

#### Scenario: Convert 5-class to 3-class

**Given** PhoBERT returns:
- Rating: 5 (VERY_POSITIVE)
- Confidence: 0.92

**When** converting to ABSA format

**Then** the system SHALL return:
- Label: "POSITIVE" (score > 0.25)
- Score: 1.0 (mapped from rating 5)
- Confidence: 0.92 (preserved)

#### Scenario: Convert all 5 classes

**Given** PhoBERT ratings 1, 2, 3, 4, 5

**When** converting to ABSA format

**Then** the system SHALL map:
- Rating 1 (VERY_NEGATIVE) → Score -1.0 → Label "NEGATIVE"
- Rating 2 (NEGATIVE) → Score -0.5 → Label "NEGATIVE"
- Rating 3 (NEUTRAL) → Score 0.0 → Label "NEUTRAL"
- Rating 4 (POSITIVE) → Score 0.5 → Label "POSITIVE"
- Rating 5 (VERY_POSITIVE) → Score 1.0 → Label "POSITIVE"

#### Scenario: Apply thresholds for label assignment

**Given** aggregated score: 0.15

**When** assigning label

**Then** the system SHALL:
- Compare score to thresholds (POSITIVE: >0.25, NEGATIVE: <-0.25)
- Return label: "NEUTRAL" (score between -0.25 and 0.25)

---

### Requirement: Weighted Aggregation

The Analytics Engine SHALL aggregate multiple sentiment predictions for the same aspect using confidence-weighted average.

**Rationale**: When an aspect is mentioned multiple times, we need a single representative sentiment. Weighted average respects model confidence.

#### Scenario: Aggregate multiple mentions with different confidences

**Given** PERFORMANCE aspect has 2 mentions:
- Mention 1: {score: -0.8, confidence: 0.95}
- Mention 2: {score: -0.6, confidence: 0.70}

**When** aggregating scores

**Then** the system SHALL:
- Calculate weighted average: (-0.8 × 0.95 + -0.6 × 0.70) / (0.95 + 0.70) = -0.71
- Assign label: "NEGATIVE" (score < -0.25)
- Return mentions count: 2
- Return average confidence: (0.95 + 0.70) / 2 = 0.825

#### Scenario: Aggregate conflicting sentiments

**Given** PRICE aspect has 2 mentions:
- Mention 1: {score: 0.8, confidence: 0.90} (POSITIVE)
- Mention 2: {score: -0.7, confidence: 0.85} (NEGATIVE)

**When** aggregating scores

**Then** the system SHALL:
- Calculate weighted average: (0.8 × 0.90 + -0.7 × 0.85) / (0.90 + 0.85) = 0.09
- Assign label: "NEUTRAL" (score between -0.25 and 0.25)
- Return mentions count: 2
- Note: Conflicting sentiments cancel out, resulting in neutral

---

### Requirement: Output Format

The Analytics Engine SHALL return structured output with overall sentiment and aspect-level sentiments.

**Rationale**: Structured output enables downstream processing (ImpactCalculator, database storage, API responses).

#### Scenario: Return complete analysis result

**Given** analysis completes successfully

**When** returning result

**Then** the system SHALL return dictionary with structure:
```python
{
    "overall": {
        "label": "NEUTRAL" | "POSITIVE" | "NEGATIVE",
        "score": float,  # -1.0 to 1.0
        "confidence": float,  # 0.0 to 1.0
        "probabilities": {
            "POSITIVE": float,
            "NEGATIVE": float,
            "NEUTRAL": float
        }
    },
    "aspects": {
        "DESIGN": {
            "label": "POSITIVE" | "NEGATIVE" | "NEUTRAL",
            "score": float,
            "confidence": float,
            "mentions": int,
            "keywords": List[str]
        },
        # ... other aspects if present
    }
}
```

#### Scenario: Return overall only when no keywords

**Given** keywords list is empty

**When** returning result

**Then** the system SHALL:
- Return overall sentiment (always available)
- Return empty aspects dict: {}
- Log info message (not error)

---

### Requirement: Error Handling and Graceful Degradation

The Analytics Engine SHALL handle errors gracefully without crashing the pipeline.

**Rationale**: Production systems must be resilient. Errors in aspect analysis should not block overall sentiment.

#### Scenario: Handle PhoBERT prediction failure

**Given** PhoBERT ONNX model fails to predict (exception raised)

**When** analyzing sentiment

**Then** the system SHALL:
- Catch exception
- Log error with context
- Return overall sentiment if available (fallback)
- Return empty aspects dict or skip failed aspects
- Continue processing (do not raise exception to caller)

#### Scenario: Handle context extraction failure

**Given** context extraction fails (e.g., keyword position invalid)

**When** analyzing aspect sentiment

**Then** the system SHALL:
- Use full text as fallback context
- Log warning
- Continue processing other aspects
- Return result for successfully processed aspects

---

### Requirement: Performance

The Analytics Engine SHALL complete aspect-based sentiment analysis within acceptable time limits.

**Rationale**: Real-time or near-real-time processing is required for social media monitoring.

#### Scenario: Process post with 3 aspects

**Given**:
- Text length: 200 characters
- Keywords: 3 (one per aspect: DESIGN, PRICE, PERFORMANCE)

**When** analyzing sentiment

**Then** the system SHALL:
- Complete overall sentiment: <100ms
- Complete aspect sentiment (3 aspects): <300ms
- Total time: <500ms per post

**Note**: Performance target is per-post, not per-aspect. Multiple inferences are expected.

---

### Requirement: Configuration

The Analytics Engine SHALL allow configuration of context window size and sentiment thresholds.

**Rationale**: Different use cases may require different window sizes or sensitivity thresholds.

#### Scenario: Configure context window size

**Given** configuration: `CONTEXT_WINDOW_SIZE = 80`

**When** extracting context windows

**Then** the system SHALL use 80 characters (instead of default 60)

#### Scenario: Configure sentiment thresholds

**Given** configuration:
- `THRESHOLD_POSITIVE = 0.3`
- `THRESHOLD_NEGATIVE = -0.3`

**When** assigning labels

**Then** the system SHALL:
- Use 0.3 as positive threshold (instead of default 0.25)
- Use -0.3 as negative threshold (instead of default -0.25)

### Requirement: Sentiment Model Semantic Correctness

The Analytics Engine SHALL ensure that the underlying sentiment model used by the ABSA pipeline
produces semantically correct labels for clearly positive and negative Vietnamese texts.

**Rationale**: Even with a correct architecture, an improperly configured or incompatible model
(e.g., wrong base model or missing special tokens) can yield consistently wrong sentiment
predictions. This requirement makes semantic correctness an explicit contract, not just
structural validity.

#### Scenario: Detect negative price sentiment

**Given** the text "Xe thiết kế rất đẹp nhưng giá quá đắt"  
**And** keywords mapped as:
- "thiết kế" → aspect="DESIGN"  
- "giá" → aspect="PRICE"

**When** running the ABSA pipeline end-to-end  
**Then** the system SHALL:
- Assign a POSITIVE sentiment label to DESIGN aspect with a score > 0  
- Assign a NEGATIVE sentiment label to PRICE aspect with a score < 0

#### Scenario: Detect overall negative sentiment

**Given** one of the following texts:
- "Sản phẩm dở tệ"  
- "Chất lượng kém"  
- "Rất tệ, không nên mua"  

**When** analyzing overall sentiment (without aspect keywords)  
**Then** the system SHALL:
- Assign overall label NEGATIVE (or VERY_NEGATIVE for 5-class models)  
- Return an overall score < 0

#### Scenario: Distinguish positive and negative aspects in mixed text

**Given** the text "Thiết kế rất đẹp nhưng pin yếu và giá cao"  
**And** keywords mapped as:
- "thiết kế" → aspect="DESIGN"  
- "pin" → aspect="PERFORMANCE"  
- "giá" → aspect="PRICE"  

**When** running aspect-based sentiment analysis  
**Then** the system SHALL:
- Assign a POSITIVE sentiment label to DESIGN aspect with a positive score  
- Assign NEGATIVE sentiment labels to both PERFORMANCE (pin) and PRICE aspects with negative scores

