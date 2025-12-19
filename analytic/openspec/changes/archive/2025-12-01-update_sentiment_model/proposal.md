# Change: Update Sentiment Model for ABSA (PhoBERT → Fine-tuned Sentiment Model)

**Change ID**: `update_sentiment_model`  
**Status**: Draft  
**Related Spec**: `aspect_based_sentiment`  
**Context Docs**: `problem/evaluation.md`, `problem/ACTION_PLAN.md`, `problem/QUICK_FIX.md`, `problem/model_fix_proposal.md`, `problem/refactor_sentiment_model.md`

## Why

Despite a robust architecture and passing tests, the current PhoBERT ONNX sentiment model is
failing semantically:

- Real examples show **PRICE** and **PERFORMANCE** aspects being labeled POSITIVE even when the
  text clearly expresses negative sentiment (e.g., "giá quá cao", "pin thì hơi yếu").
- Model outputs are heavily skewed toward `VERY_POSITIVE` (~99% confidence) for almost all inputs.
- Integration tests were previously too weak, only validating structure (types, presence of fields)
  but not the **correctness of sentiment labels**.

As a result, Module 4 (ABSA) looks successful from a code/testing perspective but produces
fundamentally wrong business insights. This change aims to **fix the sentiment model itself** and
strengthen tests so that semantic failures are caught.

## What Changes

- **Tokenization Fix** for PhoBERT ONNX:
  - Add `add_special_tokens=True` to all tokenizer calls feeding the ONNX model.
  - Ensure PhoBERT receives `<s>` and `</s>` special tokens as in training.
- **Model Verification & Swap**:
  - Verify the current ONNX model metadata in `infrastructure/phobert/models/config.json`.
  - If it is a base masked language model (e.g., `vinai/phobert-base` without classification head),
    replace it with a **proper Vietnamese sentiment model** (e.g., `wonrax/phobert-base-vietnamese-sentiment`
    or `uit-nlp/vietnamese-sentiment-analysis`) converted to ONNX.
  - Align `SENTIMENT_MAP` and `SENTIMENT_LABELS` in `infrastructure/ai/constants.py` with the new
    model's label space (3-class or 5-class).
- **Adapter Logic Update**:
  - Update `PhoBERTONNX` post-processing to correctly interpret logits from the new model
    (3 logits for NEG/NEU/POS instead of 5, if applicable).
  - Keep the existing `rating` (1–5), `sentiment` label, and `confidence` contract stable for
    downstream consumers.
- **Strengthen Integration Tests**:
  - Tighten `tests/sentiment/test_integration.py` assertions to check **semantic correctness**:
    - "Thiết kế đẹp" → DESIGN aspect MUST be POSITIVE.
    - "Giá quá đắt" → PRICE aspect MUST be NEGATIVE.
    - Negative sentences ("Sản phẩm dở tệ", "Chất lượng kém") MUST map to NEGATIVE overall.
  - Ensure tests fail loudly if the model deviates from expected behaviour.
- **Keep ABSA API Stable**:
  - No changes to `SentimentAnalyzer` public interface or output schema.
  - Only adapter, constants, and tests are updated to align with the new model.

## Impact

- **Specs**:
  - `aspect_based_sentiment` remains the primary capability; this change refines its implementation
    and adds a new requirement around **semantic correctness** of the underlying model.
- **Code**:
  - `infrastructure/ai/phobert_onnx.py`: Tokenization and post-processing logic.
  - `infrastructure/ai/constants.py`: Model path, label/score mapping.
  - `tests/sentiment/test_integration.py`: Stronger semantic assertions.
  - (Optional) `tests/phobert/*`: Additional unit/performance tests for the new model.
- **Business**:
  - Sentiment analytics becomes trustworthy: DESIGN, PRICE, PERFORMANCE aspects will have labels
    that match human intuition.
  - Prevents "green tests, wrong AI" situations by making tests semantics-aware.

