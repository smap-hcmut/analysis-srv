## 1. Implementation

### 1.1 Teencode Normalizer
- [x] 1.1.1 Add `teencode_dict` dictionary to `TextPreprocessor.__init__()` with 20-30 common Vietnamese slang terms
- [x] 1.1.2 Implement `_normalize_teencode()` helper method using word-boundary regex (`\b`)
- [x] 1.1.3 Integrate teencode normalization into `normalize()` method (before punctuation removal)
- [x] 1.1.4 Add unit tests for teencode replacement (test `ko` → `không`, `vkl` → `rất`, `ae` → `anh em`)

### 1.2 NFKC Normalization
- [x] 1.2.1 Change `unicodedata.normalize('NFC', text)` to `unicodedata.normalize('NFKC', text)` in `normalize()` method
- [x] 1.2.2 Verify Vietnamese diacritics still preserved correctly
- [x] 1.2.3 Add unit test for special font conversion (`𝐻𝑜𝑡` → `hot`)
- [x] 1.2.4 Run Case 8 test to verify fix

### 1.3 Enhanced Spam Detection
- [x] 1.3.1 Add Vietnamese phone number regex pattern to `__init__()`: `(03|05|07|08|09|01[2|6|8|9])+([0-9]{8})`
- [x] 1.3.2 Add spam keywords list: `["vay vốn", "lãi suất", "giải ngân", "bán sim", "tuyển dụng"]`
- [x] 1.3.3 Implement `_detect_spam_signals()` helper method
- [x] 1.3.4 Add `has_phone` and `has_spam_keyword` to `calculate_stats()` return dictionary
- [x] 1.3.5 Add unit tests for phone detection and spam keyword detection
- [x] 1.3.6 Run Case 5 test to verify spam signals appear

### 1.4 Merge Cleanup Logic
- [x] 1.4.1 Update `merge_content()` to strip whitespace and trailing punctuation from each part before joining
- [x] 1.4.2 Add regex to remove duplicate periods (`..` → `.`) after joining
- [x] 1.4.3 Add unit tests for merge cleanup (test no duplicate periods, clean separation)
- [x] 1.4.4 Run Case 7 test to verify fix

## 2. Testing

- [x] 2.1 Run all existing unit tests (should pass without modification)
- [x] 2.2 Run `examples/preprocess_example.py` with all 8 test cases
- [x] 2.3 Verify Case 4 output: teencode normalized (`ko` → `không`)
- [x] 2.4 Verify Case 5 output: `has_phone=True`, `has_spam_keyword=True` in stats
- [x] 2.5 Verify Case 6 output: Unicode still works (NFC preserved)
- [x] 2.6 Verify Case 7 output: No duplicate periods, clean separation
- [x] 2.7 Verify Case 8 output: Special fonts converted (`𝐻𝑜𝑡` → `hot`), not lost

## 3. Validation

- [x] 3.1 Performance benchmark: Verify processing time < 10ms per post (p95)
- [x] 3.2 Review test output for all cases matches expected results
- [x] 3.3 Verify no regressions in existing functionality
- [x] 3.4 Run `openspec validate update_text_preprocessor --strict` and resolve issues

