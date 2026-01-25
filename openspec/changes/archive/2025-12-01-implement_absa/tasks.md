# Tasks: Implement Aspect-Based Sentiment Analyzer (ABSA)

## Implementation Checklist

### Phase 1: Core Implementation

- [x] **Task 1.1**: Create `services/analytics/sentiment/` directory structure
  - Create `__init__.py`
  - Create `sentiment_analyzer.py`
  - Add to `services/analytics/__init__.py` exports

- [x] **Task 1.2**: Add configuration constants
  - Add `CONTEXT_WINDOW_SIZE` to `infrastructure/ai/constants.py` (default: 60)
  - Add `THRESHOLD_POSITIVE` and `THRESHOLD_NEGATIVE` (default: 0.25, -0.25)
  - Add `SCORE_MAP` for 5-class to numeric conversion
  - Update `core/config.py` if needed for environment variable overrides

- [x] **Task 1.3**: Implement `SentimentAnalyzer` class skeleton
  - `__init__(phobert_model: PhoBERTONNX)` constructor
  - `analyze(text: str, keywords: List[Dict]) -> Dict` main method
  - Type hints and docstrings

- [x] **Task 1.4**: Implement overall sentiment analysis
  - Call `PhoBERTONNX.predict(text)` for full text
  - Convert 5-class result to 3-class format (POSITIVE/NEGATIVE/NEUTRAL)
  - Return with confidence and probabilities

- [x] **Task 1.5**: Implement context window extraction
  - `_extract_smart_window(text: str, keyword: str, position: int) -> str`
  - Extract ±N characters around keyword
  - Smart boundary snapping (expand to nearest whitespace/punctuation)
  - Handle edge cases (keyword not found, text too short)

- [x] **Task 1.6**: Implement aspect-based sentiment analysis
  - `_analyze_aspect(text: str, keywords: List[Dict]) -> Dict`
  - Group keywords by aspect
  - For each keyword: extract context, call PhoBERT, convert to score
  - Return per-aspect results

- [x] **Task 1.7**: Implement weighted aggregation
  - `_aggregate_scores(results: List[Dict]) -> Dict`
  - Calculate weighted average: `Σ(score × confidence) / Σ(confidence)`
  - Map aggregated score to label (POSITIVE/NEGATIVE/NEUTRAL)
  - Include mention count and keywords list

- [x] **Task 1.8**: Implement helper methods
  - `_convert_to_absa_format(phobert_result: Dict) -> Dict` (5-class → 3-class)
  - `_group_keywords_by_aspect(keywords: List[Dict]) -> Dict`
  - `_map_score_to_label(score: float) -> str`

### Phase 2: Error Handling & Edge Cases

- [x] **Task 2.1**: Add error handling for context extraction
  - Handle keyword not found in text
  - Handle text too short for context window
  - Fallback to full text if context extraction fails

- [x] **Task 2.2**: Add error handling for PhoBERT prediction
  - Try-catch around `PhoBERTONNX.predict()` calls
  - Graceful degradation: use overall sentiment as fallback
  - Log warnings for debugging

- [x] **Task 2.3**: Handle empty/missing inputs
  - Empty text → return neutral sentiment
  - Empty keywords → return overall sentiment only
  - Missing aspect in keywords → skip aspect analysis

### Phase 3: Testing

- [x] **Task 3.1**: Create unit tests (`tests/sentiment/test_unit.py`)
  - Test context extraction (various scenarios)
  - Test score conversion (all 5 classes)
  - Test aggregation (single mention, multiple mentions)
  - Test edge cases (empty text, missing keywords)
  - Mock `PhoBERTONNX` for isolated testing

- [x] **Task 3.2**: Create integration tests (`tests/sentiment/test_integration.py`)
  - Test with real PhoBERT model (skip if not available)
  - Test overall sentiment on Vietnamese text
  - Test aspect sentiment on real examples
  - Test conflict scenarios (positive and negative for same aspect)
  - Test multiple aspects in one text

- [x] **Task 3.3**: Create performance tests (`tests/sentiment/test_performance.py`)
  - Benchmark overall sentiment inference time
  - Benchmark aspect sentiment (per keyword)
  - Benchmark full analysis (overall + 3 aspects)
  - Memory usage profiling

- [x] **Task 3.4**: Create example script (`examples/sentiment_example.py`)
  - Demonstrate usage with real Vietnamese text
  - Show conflict scenario example
  - Show aggregation example

### Phase 4: Documentation & Validation

- [x] **Task 4.1**: Add docstrings and type hints
  - Complete docstrings for all public methods
  - Add usage examples in docstrings
  - Ensure type hints are complete

- [x] **Task 4.2**: Update README or documentation
  - Document `SentimentAnalyzer` usage
  - Add configuration options
  - Add examples

- [x] **Task 4.3**: Run linter and fix issues
  - Run `ruff check` and fix issues
  - Run `mypy` and fix type errors
  - Ensure code follows project conventions

- [x] **Task 4.4**: Validate against spec
  - Review `specs/aspect_based_sentiment/spec.md`
  - Ensure all requirements are met
  - Run `openspec validate implement_absa --strict`

### Phase 5: Integration Preparation

- [x] **Task 5.1**: Verify integration points
  - Test with `KeywordExtractor` output format
  - Ensure `Aspect` enum compatibility
  - Test with `TextPreprocessor` output format

- [x] **Task 5.2**: Add to Makefile (if needed)
  - Add test command: `make test-sentiment`
  - Add example command: `make example-sentiment`

- [x] **Task 5.3**: Update `.env.example` (if needed)
  - Add sentiment-related configuration variables

## Validation Checklist

Before marking tasks complete, verify:

- [x] All unit tests pass (`pytest tests/sentiment/test_unit.py`)
- [x] Integration tests pass (if model available)
- [x] Performance targets met (<500ms per post with 3 aspects)
- [x] Code coverage >90% for core logic
- [x] No linter errors
- [x] Documentation complete
- [x] Spec validation passes (`openspec validate implement_absa --strict`)

## Dependencies

- ✅ `infrastructure/ai/phobert_onnx.py` - Must be available
- ✅ `services/analytics/keyword/keyword_extractor.py` - For keyword format
- ✅ `core/config.py` - For configuration

## Estimated Effort

- **Phase 1**: 4-6 hours (core implementation)
- **Phase 2**: 1-2 hours (error handling)
- **Phase 3**: 3-4 hours (testing)
- **Phase 4**: 1-2 hours (documentation)
- **Phase 5**: 1 hour (integration prep)

**Total**: 10-15 hours

