# Enhance Hybrid Keyword Extraction

**Change ID**: `enhance_hybrid_keyword_extraction`  
**Status**: Proposal  
**Created**: 2025-11-30  
**Author**: Analytics Engine Team

## Why

The current keyword extraction implementation (`infrastructure/ai/spacyyake_extractor.py`) uses a pure AI approach (SpaCy + YAKE). While this works well for general keyword discovery, it has limitations for domain-specific analytics:

1. **Low Recall for Domain Keywords**: May miss critical industry terms like "pin", "sạc", "bảo hành" that are essential for automotive analytics
2. **No Aspect Mapping**: Keywords are extracted but not categorized into business-relevant aspects (DESIGN, PERFORMANCE, PRICE, SERVICE)
3. **Inconsistent Results**: Statistical methods can produce varying results for the same domain concepts

**Business Impact**: Without aspect-aware keyword extraction, downstream sentiment analysis cannot provide actionable insights like "Customers are negative about PRICE but positive about DESIGN."

---

## What Changes

### New Service Layer
- **Create**: `services/analytics/keyword/` directory
- **Create**: `services/analytics/keyword/__init__.py`
- **Create**: `services/analytics/keyword/keyword_extractor.py` - Service wrapper with hybrid logic
- **Create**: `config/aspects.yaml` - Domain-specific keyword dictionary

### Configuration
- **Update**: `core/config.py` - Add aspect dictionary path and hybrid extraction settings

### Testing
- **Create**: `tests/keyword/` directory
- **Create**: `tests/keyword/test_unit.py` - Unit tests for hybrid logic
- **Create**: `tests/keyword/test_integration.py` - Integration tests with real Vietnamese text
- **Create**: `tests/keyword/test_performance.py` - Performance benchmarks

### Documentation
- **Update**: `README.md` - Add Hybrid Keyword Extraction section
- **Create**: `examples/keyword_extractor_example.py` - Usage examples

---

## Problem

Current keyword extraction has three main issues:

### 1. Missing Domain Keywords
**Example**:
```
Input: "VinFast lỗi pin sạc không vào"
Current Output: ["vinfast", "lỗi"] (generic)
Desired Output: ["pin" (PERFORMANCE), "sạc" (PERFORMANCE), "lỗi" (PERFORMANCE)]
```

### 2. No Aspect Categorization
Keywords are flat lists without business context. Analysts cannot answer:
- "What aspects do customers complain about most?"
- "Is PRICE sentiment improving over time?"

### 3. Inconsistent Coverage
Pure statistical methods may miss important but less frequent domain terms.

---

## Proposed Solution

### Architecture: 3-Stage Hybrid Funnel

```
┌─────────────────────────────────────────┐
│  Input: "Xe đẹp nhưng pin yếu quá"     │
└─────────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────┐
│  Stage 1: Dictionary Matching          │
│  - Fast O(n) lookup in aspect dict     │
│  - 100% precision for known terms      │
│  Output: ["pin"→PERFORMANCE]            │
└─────────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────┐
│  Stage 2: AI Discovery (if needed)     │
│  - Use existing SpacyYakeExtractor     │
│  - Filter: Nouns/Proper Nouns only     │
│  - Score: YAKE statistical ranking     │
│  Output: ["xe"→GENERAL, "đẹp"→DESIGN]  │
└─────────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────┐
│  Stage 3: Aspect Mapping               │
│  - Fuzzy match AI keywords to aspects  │
│  - Fallback to GENERAL if no match     │
│  Final: All keywords have aspects      │
└─────────────────────────────────────────┘
```

### Aspect Dictionary Structure

```yaml
# config/aspects.yaml
DESIGN:
  primary: ["thiết kế", "ngoại thất", "nội thất", "màu xe", "đèn", "vô lăng"]
  secondary: ["đẹp", "xấu", "sang", "nhựa", "thô"]

PERFORMANCE:
  primary: ["pin", "sạc", "trạm sạc", "động cơ", "tốc độ", "gia tốc"]
  secondary: ["yếu", "mạnh", "lỗi", "treo", "lag"]

PRICE:
  primary: ["giá", "tiền", "chi phí", "lăn bánh", "cọc", "thuê pin"]
  secondary: ["đắt", "rẻ", "hời", "chát"]

SERVICE:
  primary: ["bảo hành", "nhân viên", "showroom", "cứu hộ", "xưởng", "3s"]
  secondary: ["thái độ", "chậm", "nhiệt tình"]
```

### Service Layer Design

```python
# services/analytics/keyword/keyword_extractor.py

class KeywordExtractor:
    """Hybrid keyword extractor with aspect mapping."""
    
    def __init__(self):
        # Reuse existing infrastructure
        self.ai_extractor = SpacyYakeExtractor()  # From infrastructure/ai
        self.aspect_dict = self._load_aspects()
        self.keyword_map = self._build_lookup_map()
    
    def extract(self, text: str) -> ExtractionResult:
        """
        Extract keywords with aspect mapping.
        
        Returns:
            ExtractionResult with keywords list:
            [
                {
                    "keyword": "pin",
                    "aspect": "PERFORMANCE",
                    "score": 1.0,
                    "source": "DICT"
                },
                {
                    "keyword": "vinfast",
                    "aspect": "GENERAL",
                    "score": 0.85,
                    "source": "AI"
                }
            ]
        """
```

---

## Scope

### In Scope
- ✅ Service layer wrapper in `services/analytics/keyword/`
- ✅ Dictionary-based matching with `config/aspects.yaml`
- ✅ Aspect mapping for all keywords (DICT + AI)
- ✅ Integration with existing `SpacyYakeExtractor`
- ✅ Comprehensive test suite (30+ tests)
- ✅ Performance benchmarks (<50ms target)

### Out of Scope
- ❌ Modifying existing `infrastructure/ai/spacyyake_extractor.py`
- ❌ Machine learning-based aspect classification
- ❌ Multi-language support (Vietnamese only)
- ❌ Real-time dictionary updates (hot-reload can be added later)

---

## Success Criteria

### Functional Requirements
- [ ] Dictionary matching correctly identifies all terms in `aspects.yaml`
- [ ] AI discovery finds keywords not in dictionary
- [ ] All keywords have aspect labels (no unlabeled keywords)
- [ ] Fuzzy matching maps similar terms to correct aspects
- [ ] Handles edge cases (empty text, no keywords, all stopwords)

### Non-Functional Requirements
- [ ] Processing time <50ms per text (including AI extraction)
- [ ] Dictionary lookup <1ms (O(n) complexity)
- [ ] Test coverage >90%
- [ ] Memory usage <50MB (dictionary + models)

### Integration Requirements
- [ ] Exports clean interface from `services/analytics/keyword/__init__.py`
- [ ] Compatible with existing pipeline (TextPreprocessor → Intent → Keyword)
- [ ] Configuration via `core/config.py`
- [ ] Example script demonstrates all features

---

## Implementation Plan

### Phase 1: Core Implementation (1 day)
1. Create `services/analytics/keyword/` structure
2. Implement `KeywordExtractor` class with hybrid logic
3. Create `config/aspects.yaml` with initial dictionary
4. Add configuration to `core/config.py`

### Phase 2: Testing (1 day)
1. Unit tests for dictionary matching
2. Unit tests for aspect mapping
3. Integration tests with real Vietnamese text
4. Performance benchmarks

### Phase 3: Documentation & Integration (0.5 day)
1. Update README.md
2. Create example script
3. Add docstrings and type hints
4. Prepare for orchestrator integration

### Phase 4: Validation (0.5 day)
1. Run `openspec validate --strict`
2. Code quality checks
3. Final review

**Total Estimated Effort**: 2-3 days

---

## Dependencies

**Requires**:
- ✅ `infrastructure/ai/spacyyake_extractor.py` (already exists)
- ✅ `services/analytics/preprocessing/` (Module 1, completed)
- ✅ `services/analytics/intent/` (Module 2, completed)

**Blocks**:
- Sentiment analysis module (Module 4) - needs aspect-aware keywords

---

## Risks

### Risk 1: Dictionary Maintenance Overhead
**Mitigation**: Start with core 50-100 terms, expand based on production data

### Risk 2: Performance Impact
**Mitigation**: Dictionary lookup is O(n), AI extraction only runs if needed (<5 dict matches)

### Risk 3: Aspect Mapping Accuracy
**Mitigation**: Fuzzy matching with fallback to GENERAL aspect, can be improved iteratively

---

## Alternatives Considered

### Alternative 1: Pure Dictionary Approach
**Pros**: Fastest, 100% precision  
**Cons**: Zero recall for new/trending keywords  
**Decision**: Rejected - too rigid for evolving language

### Alternative 2: Pure AI Approach (Current)
**Pros**: Discovers new keywords automatically  
**Cons**: Misses domain-specific terms, no aspect mapping  
**Decision**: Rejected - insufficient for domain analytics

### Alternative 3: ML-based Aspect Classification
**Pros**: Could learn aspects automatically  
**Cons**: Requires training data, complex, slower  
**Decision**: Deferred to Phase 2 - start with hybrid rule-based

---

## Open Questions

None - requirements are clear from `term.md` and existing implementation.

---

## Evaluation & Improvement Plan

### Architecture Review Results (Score: 8/10)

**Date**: 2025-12-01
**Reviewer**: Architecture Senior
**Status**: Phase 1-2 Complete, Improvements Needed for Phase 3

#### Strengths Identified ✅

1. **Dictionary Matching Excellence**
   - 100% accuracy for domain-specific terms (pin, sạc, giá, bảo hành)
   - Correct aspect mapping (pin → PERFORMANCE, giá → PRICE)
   - Serves as reliable safety net (80% coverage even if AI fails)

2. **Exceptional Performance**
   - 78,555 posts/second (0.01ms per post)
   - Faster than Intent Classifier (regex-based)
   - Optimized hash map data structure confirmed

3. **Clear Aspect Distribution**
   - Clean separation of keywords by aspect
   - Ready for Module 4 (Aspect-Based Sentiment Analysis)

#### Issues Identified ❌

1. **AI Discovery Environment Error** (Critical)
   - SpaCy model `en_core_web_sm` fails to download in uv environment
   - Wrong model: should use Vietnamese (`vi_core_news_lg`) not English
   - Impact: AI discovery disabled, cannot find trending keywords

2. **Dictionary Over-Coverage** (Warning)
   - Generic adjectives (tốt, xấu, nhanh, chậm) cause misclassification
   - Example: "Giá tốt" → `tốt:SERVICE` instead of focusing on PRICE
   - Risk: Keyword Extractor should find subjects, not determine sentiment

### Required Improvements (Phase 3)

#### Improvement 1: Fix SpaCy Vietnamese Model
- Update `infrastructure/ai/constants.py` to use `vi_core_news_lg`
- Install Vietnamese model in environment
- Verify AI discovery works with Vietnamese text

#### Improvement 2: Refine Aspect Dictionary
- Remove standalone generic adjectives from `config/aspects.yaml`
- Keep only compound/contextual terms (e.g., "sạc nhanh", "pin yếu")
- Separate concerns: Module 3 finds subjects, Module 4 analyzes sentiment

#### Improvement 3: Add AI Discovery Tests
- Test unknown technical terms (e.g., "hud kính lái")
- Test trending slang (e.g., "xe lướt")
- Test competitor brand discovery

#### Improvement 4: Update Documentation
- Document Vietnamese model requirement
- Add troubleshooting guide
- Show dictionary-only fallback mode

### Deployment Readiness

**Production Ready**:
- ✅ Dictionary matching (8/10 functionality)
- ✅ Performance exceeds targets

**Requires Fix**:
- ⚠️ SpaCy model (for 10/10 functionality)
