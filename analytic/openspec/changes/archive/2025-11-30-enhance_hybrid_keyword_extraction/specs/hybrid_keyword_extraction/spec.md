# Hybrid Keyword Extraction Capability

**Capability**: `hybrid_keyword_extraction`  
**Owner**: Analytics Engine Team  
**Status**: Proposed

---

## ADDED Requirements

### Requirement: Dictionary-Based Keyword Matching

The Analytics Engine SHALL extract keywords using a domain-specific dictionary with aspect categorization.

**Rationale**: Pure AI-based extraction may miss critical industry terms. A dictionary ensures 100% recall for known domain keywords (e.g., "pin", "sạc", "bảo hành") which are essential for automotive analytics.

#### Scenario: Extract known domain keywords

**Given** the aspect dictionary contains:
```yaml
PERFORMANCE:
  primary: ["pin", "sạc", "động cơ"]
```

**When** processing text "VinFast lỗi pin sạc không vào"

**Then** the system SHALL extract:
- keyword="pin", aspect="PERFORMANCE", source="DICT", score=1.0
- keyword="sạc", aspect="PERFORMANCE", source="DICT", score=1.0

#### Scenario: Handle case-insensitive matching

**Given** dictionary contains "Pin" (capitalized)

**When** processing text "pin yếu quá"

**Then** the system SHALL match "pin" (lowercase) to dictionary entry

#### Scenario: Match multi-word terms

**Given** dictionary contains "trạm sạc"

**When** processing text "tìm trạm sạc gần đây"

**Then** the system SHALL extract keyword="trạm sạc", aspect="PERFORMANCE"

---

### Requirement: AI-Based Keyword Discovery

The Analytics Engine SHALL discover new keywords using SpaCy + YAKE when dictionary coverage is insufficient.

**Rationale**: Language evolves and new terms emerge (e.g., brand names, slang). AI extraction ensures we don't miss trending keywords not yet in the dictionary.

#### Scenario: Discover keywords not in dictionary

**Given** dictionary does not contain "VinFast"

**When** processing text "VinFast ra mẫu mới"

**Then** the system SHALL:
- Use SpaCy to identify "VinFast" as PROPN (proper noun)
- Use YAKE to score relevance
- Extract keyword="VinFast", source="AI"

#### Scenario: Filter noise with SpaCy POS tagging

**Given** text contains stopwords and function words

**When** processing text "tuy nhiên thì là mà rằng"

**Then** the system SHALL:
- Filter out all stopwords using SpaCy
- Return empty keyword list (no NOUN/PROPN found)

#### Scenario: Trigger AI extraction only when needed

**Given** dictionary matching found 6 keywords

**When** processing text

**Then** the system SHALL NOT run AI extraction (threshold is 5 keywords)

**Given** dictionary matching found 3 keywords

**When** processing text

**Then** the system SHALL run AI extraction to discover more keywords

---

### Requirement: Aspect Mapping for All Keywords

The Analytics Engine SHALL assign an aspect label to every extracted keyword.

**Rationale**: Downstream sentiment analysis needs aspect context to provide actionable insights (e.g., "Customers are negative about PRICE but positive about DESIGN").

#### Scenario: Map dictionary keywords to aspects

**Given** dictionary defines:
```yaml
PRICE:
  primary: ["giá", "tiền"]
```

**When** extracting keyword "giá" from dictionary

**Then** the system SHALL assign aspect="PRICE"

#### Scenario: Fuzzy map AI keywords to aspects

**Given** dictionary contains "thiết kế" → DESIGN

**When** AI discovers keyword "thiết kế đẹp"

**Then** the system SHALL:
- Fuzzy match "thiết kế" substring
- Assign aspect="DESIGN"

#### Scenario: Fallback to GENERAL aspect

**Given** AI discovers keyword "VinFast"

**When** no fuzzy match found in dictionary

**Then** the system SHALL assign aspect="GENERAL"

---

### Requirement: Hybrid Extraction Logic

The Analytics Engine SHALL combine dictionary and AI extraction with proper prioritization.

**Rationale**: Dictionary provides precision, AI provides recall. Combining both gives optimal coverage.

#### Scenario: Dictionary keywords have priority

**Given** both dictionary and AI extract "pin"

**When** combining results

**Then** the system SHALL:
- Keep dictionary version (source="DICT", score=1.0)
- Discard AI duplicate

#### Scenario: Combine unique keywords from both sources

**Given** dictionary extracts ["pin", "sạc"]  
**And** AI extracts ["VinFast", "xe"]

**When** combining results

**Then** the system SHALL return all 4 keywords with correct sources

---

### Requirement: Performance Optimization

The Analytics Engine SHALL extract keywords efficiently to avoid pipeline bottlenecks.

**Rationale**: Keyword extraction is called for every post. Slow extraction blocks the entire pipeline.

#### Scenario: Dictionary lookup under 1ms

**Given** dictionary contains 100 terms

**When** processing typical text (200 words)

**Then** dictionary matching SHALL complete in <1ms

#### Scenario: Total extraction under 50ms

**Given** text requires both dictionary and AI extraction

**When** processing typical text (200 words)

**Then** total extraction time SHALL be <50ms

#### Scenario: Batch processing efficiency

**Given** 100 posts to process

**When** extracting keywords in batch

**Then** average time per post SHALL be <30ms

---

### Requirement: Output Contract

The Analytics Engine SHALL return keyword extraction results in a standardized format.

**Rationale**: Consistent output format enables easy integration with downstream modules (sentiment analysis, reporting).

#### Scenario: Return structured keyword list

**When** extracting keywords from any text

**Then** the system SHALL return ExtractionResult with:
```python
{
    "keywords": [
        {
            "keyword": str,      # The extracted term
            "aspect": str,       # DESIGN|PERFORMANCE|PRICE|SERVICE|GENERAL
            "score": float,      # Confidence 0.0-1.0
            "source": str,       # DICT|AI
            "rank": int          # Position in sorted list
        }
    ],
    "metadata": {
        "dict_matches": int,     # Count from dictionary
        "ai_matches": int,       # Count from AI
        "total_keywords": int,   # Total unique keywords
        "extraction_time_ms": float
    },
    "success": bool,
    "error_message": str | None
}
```

#### Scenario: Handle empty input gracefully

**Given** text is empty or None

**When** extracting keywords

**Then** the system SHALL return:
- success=True
- keywords=[]
- metadata with zero counts

#### Scenario: Handle extraction errors

**Given** SpaCy model fails to load

**When** attempting AI extraction

**Then** the system SHALL:
- Return success=False
- Set error_message with details
- Still return dictionary matches if available
