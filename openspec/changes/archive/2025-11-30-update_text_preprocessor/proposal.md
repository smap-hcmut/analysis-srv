# Update Text Preprocessor

**Change ID**: `update_text_preprocessor`  
**Status**: Proposal  
**Created**: 2025-12-01  
**Author**: Analytics Engine Team

---

## Why

Senior architecture review of the TextPreprocessor module identified **4 critical weaknesses** that prevent production readiness, especially for Vietnamese text and spam detection:

1. **Teencode/Slang Handling**: Words like `ko` (không), `vkl` (rất), `ae` (anh em) remain unchanged, reducing PhoBERT sentiment accuracy since the model was trained on formal Vietnamese text.

2. **Insufficient Spam Detection**: Current metadata only includes `hashtag_ratio`, which misses sophisticated spam patterns (e.g., loan advertisements with phone numbers, SEO spam keywords). This causes unnecessary AI processing costs.

3. **Special Font Failure**: Mathematical Alphanumeric Symbols (e.g., `𝐻𝑜𝑡 𝑇𝑟𝑒𝑛𝑑`) are completely stripped, losing all content from stylized posts common on TikTok/Facebook.

4. **Merge Artifacts**: Extra periods and whitespace (`..`, `  . `) appear in merged text, reducing professionalism and potentially confusing tokenizers.

Current assessment: **7/10**. After these improvements: **9.5/10**.

---

## What Changes

### 1. Teencode Normalizer (NEW)
- Add dictionary-based replacement for common Vietnamese slang/abbreviations
- Replace `ko` → `không`, `vkl` → `rất`, `ae` → `anh em`, etc.
- Apply before punctuation removal to preserve word boundaries

### 2. Enhanced Spam Detection (MODIFIED)
- Add `has_phone` flag: Detect Vietnamese phone numbers (03x, 09x patterns)
- Add `has_spam_keyword` flag: Detect loan/SEO spam keywords
- Extend `stats` dictionary with these signals for orchestrator filtering

### 3. NFKC Normalization (MODIFIED)
- Change Unicode normalization from `NFC` to `NFKC` (Compatibility Decomposition)
- Converts special fonts (`𝐻𝑜𝑡` → `Hot`) while preserving Vietnamese diacritics
- Fixes Case 8 failure where stylized text was completely lost

### 4. Clean Merge Logic (MODIFIED)
- Strip whitespace and trailing punctuation from each part before joining
- Remove duplicate periods (`..` → `.`)
- Ensure clean separation between merged sections

---

## Impact

### Affected Specs
- `specs/text_preprocessing/spec.md`:
  - **ADDED**: Teencode Normalization requirement
  - **MODIFIED**: Text Normalization requirement (NFKC + cleanup)
  - **MODIFIED**: Noise Statistics requirement (spam signals)
  - **MODIFIED**: Content Merging requirement (clean separation)

### Affected Code
- `services/analytics/preprocessing/text_preprocessor.py`:
  - Add `teencode_dict` in `__init__`
  - Modify `normalize()` method (NFKC, teencode replacement)
  - Modify `calculate_stats()` method (phone/spam detection)
  - Modify `merge_content()` method (clean joining)

### Testing
- Update `examples/preprocess_example.py` test cases
- Add unit tests for teencode replacement
- Add unit tests for spam detection
- Verify NFKC handles special fonts correctly
- Verify merge cleanup removes artifacts

### Performance
- Minimal impact: Teencode dict lookup is O(1), regex patterns are pre-compiled
- Expected: <1ms additional overhead per post

---

## Non-Goals

- **Not implementing**: Full Vietnamese slang dictionary (start with most common 20-30 terms)
- **Not implementing**: Machine learning-based spam detection (rule-based only)
- **Not implementing**: Custom font detection library (rely on NFKC standard)

---

## Success Criteria

After implementation:
- ✅ Case 4 (Teencode): `ko` → `không`, `vkl` → `rất` in output
- ✅ Case 5 (Spam): `has_phone=True`, `has_spam_keyword=True` in stats
- ✅ Case 6 (Unicode): Still works correctly (NFC preserved via NFKC)
- ✅ Case 7 (Context): No duplicate periods, clean separation
- ✅ Case 8 (Special Fonts): `𝐻𝑜𝑡 𝑇𝑟𝑒𝑛𝑑` → `hot trend` (preserved, not lost)

