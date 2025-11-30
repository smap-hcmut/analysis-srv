# Design: Update Text Preprocessor

## Context

The TextPreprocessor module is Stage 1 of the AI processing pipeline. It receives raw social media posts (Atomic JSON) and produces clean, normalized text ready for PhoBERT sentiment analysis and SpaCy-YAKE keyword extraction.

**Current State**: Module works well for standard cases but fails on:
- Vietnamese slang/teencode (reduces AI accuracy)
- Sophisticated spam (wastes AI processing)
- Special Unicode fonts (loses content)
- Merge artifacts (reduces quality)

**Stakeholders**: Analytics Engine Team, AI Model Consumers (Orchestrator)

---

## Goals / Non-Goals

### Goals
1. **Improve Vietnamese Text Quality**: Normalize slang to formal Vietnamese for better PhoBERT accuracy
2. **Enhance Spam Detection**: Provide additional signals beyond `hashtag_ratio` for orchestrator filtering
3. **Preserve Special Font Content**: Convert stylized Unicode to readable text instead of losing it
4. **Clean Merge Output**: Remove artifacts (duplicate periods, extra whitespace) from merged text

### Non-Goals
- Comprehensive Vietnamese slang dictionary (start with top 20-30 terms)
- ML-based spam classification (rule-based detection only)
- Custom font detection (use standard NFKC normalization)
- Real-time dictionary updates (static dictionary in code)

---

## Decisions

### Decision 1: Teencode Dictionary Approach

**What**: Use a static dictionary with word-boundary regex replacement.

**Why**: 
- Simple, fast (O(1) lookup, pre-compiled regex)
- No external dependencies
- Easy to extend incrementally
- Word boundaries prevent false matches (e.g., `k` in `kaka`)

**Alternatives Considered**:
- ML-based slang detection: Too complex, requires training data
- External library (pyvi, underthesea): Adds dependency, may not cover slang
- Context-aware replacement: Overkill for preprocessing stage

**Implementation**:
```python
self.teencode_dict = {
    "ko": "không", "k": "không", "khg": "không", "kg": "không",
    "dc": "được", "dk": "được",
    "ae": "anh em",
    "vkl": "rất", "vcl": "rất",  # Preserve sentiment intensity
    # ... 20-30 most common terms
}
# Apply with \b word boundaries
```

---

### Decision 2: NFKC Normalization

**What**: Change from `unicodedata.normalize('NFC', text)` to `unicodedata.normalize('NFKC', text)`.

**Why**:
- NFKC (Compatibility Decomposition) converts compatibility characters to standard forms
- `𝐻𝑜𝑡` (Mathematical Bold) → `Hot` (standard)
- Preserves Vietnamese diacritics (NFC handles that)
- Standard library, no dependencies
- Fixes Case 8 failure completely

**Alternatives Considered**:
- `ftfy` library: Adds dependency, may over-correct
- Custom regex for Mathematical Alphanumeric: Complex, incomplete coverage
- Keep NFC, add separate font conversion: Redundant with NFKC

**Trade-off**: NFKC is more aggressive than NFC. It may normalize some intentional Unicode (e.g., mathematical notation), but for social media text, this is acceptable.

---

### Decision 3: Spam Detection Signals

**What**: Add `has_phone` and `has_spam_keyword` boolean flags to `stats` dictionary.

**Why**:
- Simple, rule-based (fast, no ML overhead)
- Orchestrator can combine multiple signals for filtering
- Extensible: Easy to add more patterns later
- Clear separation: Preprocessor signals, Orchestrator decides

**Patterns**:
- **Phone**: Vietnamese mobile patterns `(03|05|07|08|09|01[2|6|8|9])+([0-9]{8})`
- **Spam Keywords**: Hardcoded list `["vay vốn", "lãi suất", "giải ngân", "bán sim", "tuyển dụng"]`

**Alternatives Considered**:
- Return spam score (0-1): Less clear for boolean filtering
- Separate spam classifier: Overkill, adds complexity
- ML-based detection: Requires training data, slower

---

### Decision 4: Merge Cleanup Strategy

**What**: Clean each part (strip whitespace, remove trailing punctuation) before joining, then remove duplicate periods.

**Why**:
- Prevents artifacts at join boundaries
- Simple string operations (fast)
- Preserves intentional punctuation within parts
- Fixes Case 7 issue

**Implementation**:
```python
clean_parts = [p.strip().rstrip(".,") for p in parts if p and p.strip()]
full_text = ". ".join(clean_parts)
full_text = re.sub(r'\.\s*\.', '.', full_text)  # Remove duplicate periods
```

**Alternatives Considered**:
- Post-processing only: Doesn't fix boundary issues
- More aggressive punctuation removal: May remove intentional punctuation
- Smart punctuation insertion: Complex, may add unwanted punctuation

---

## Risks / Trade-offs

### Risk 1: NFKC Over-Normalization
**Risk**: NFKC may normalize intentional Unicode (e.g., mathematical notation in technical posts).  
**Mitigation**: Acceptable trade-off for social media content. If needed, can add allowlist for specific Unicode ranges.

### Risk 2: Teencode Dictionary Maintenance
**Risk**: Slang evolves, dictionary may become outdated.  
**Mitigation**: Start with most common terms. Can extend incrementally based on production data.

### Risk 3: False Positive Spam Detection
**Risk**: Legitimate posts mentioning "vay vốn" (loan) in context may be flagged.  
**Mitigation**: Preprocessor only signals, Orchestrator makes final decision. Can adjust keyword list based on false positive rate.

### Risk 4: Performance Impact
**Risk**: Additional regex operations may slow down preprocessing.  
**Mitigation**: All patterns pre-compiled in `__init__`. Expected overhead <1ms per post. Benchmark during implementation.

---

## Migration Plan

### Phase 1: Implementation
1. Add teencode dictionary and replacement logic
2. Change NFC → NFKC normalization
3. Add spam detection patterns and stats
4. Update merge cleanup logic

### Phase 2: Testing
1. Run existing test cases (should pass)
2. Add new unit tests for each improvement
3. Run advanced Vietnamese test cases (Cases 4-8)
4. Performance benchmark

### Phase 3: Validation
1. Review test output for all 8 cases
2. Verify no regressions in existing functionality
3. Confirm performance targets met (<10ms per post)

### Rollback
- Git revert if issues found
- No database migrations required
- No API contract changes

---

## Open Questions

1. **Teencode Dictionary Size**: Start with 20-30 terms or more?  
   **Decision**: Start with 20-30 most common, extend based on production data.

2. **Spam Keyword List**: Should this be configurable?  
   **Decision**: Hardcode initially, make configurable in future if needed.

3. **NFKC for All Text**: Should we apply NFKC only to suspicious Unicode ranges?  
   **Decision**: Apply globally. NFKC is standard and safe for social media text.

