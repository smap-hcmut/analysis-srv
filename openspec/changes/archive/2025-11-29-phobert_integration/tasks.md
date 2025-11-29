# Tasks: PhoBERT Integration

- [x] **Model Management Setup**
  - [x] Add `infrastructure/phobert/models` to `.gitignore`.
  - [x] Create `scripts/download_phobert_model.sh` for interactive MinIO download.
  - [x] Add `download-phobert` target to `Makefile`.

- [x] **Implementation**
  - [x] Add dependencies: `uv add optimum[onnxruntime] transformers pyvi torch`.
  - [x] Implement `PhoBERTONNX` class in `infrastructure/ai/phobert_onnx.py` based on README.
  - [x] Create `infrastructure/ai/__init__.py` to export the class.

- [x] **Basic Testing**
  - [x] Create `tests/test_phobert_integration.py`.
  - [x] Implement basic tests (imports, structure, error handling).
  - [x] Add `make test-phobert` command.

- [x] **Comprehensive Test Coverage**
  - [x] Add test for `_segment_text()` with Vietnamese text.
  - [x] Add test for `_tokenize()` method.
  - [x] Add test for `_postprocess()` with all 5 sentiment classes.
  - [x] Add test for `predict()` with mocked model outputs.
  - [x] Add test for `predict_batch()` method.
  - [x] Add edge case tests (empty text, long text, special characters).
  - [x] Add integration test with real model (skipped if model not downloaded).
  - [x] Add performance benchmark test.
