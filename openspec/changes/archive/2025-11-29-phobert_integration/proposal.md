# Proposal: Integrate PhoBERT ONNX Model

## Goal
Integrate the pre-trained and quantized PhoBERT ONNX model (5-class sentiment analysis) into the Analytics Engine infrastructure. This involves setting up the model download mechanism from a self-hosted MinIO, implementing a wrapper class for inference, and ensuring the model artifacts are properly managed (ignored by git).

## Context
The user has a fine-tuned PhoBERT model for sentiment analysis (5 classes: 1-5 stars) that has been converted to ONNX and quantized. This model is hosted on a private MinIO server. We need to integrate this model into the system to power the sentiment analysis capabilities of the Analytics Engine.

## Key Changes
1.  **Model Management**:
    *   Add `infrastructure/phobert/models` to `.gitignore`.
    *   Create `scripts/download_phobert_model.sh` to download artifacts from MinIO (bucket: `phobert-onnx-artifacts`) with interactive prompts for credentials.
    *   Add `make download-phobert` command.

2.  **Infrastructure Implementation**:
    *   Implement `PhoBERTONNX` class in `infrastructure/ai/phobert_onnx.py` following the logic in `infrastructure/phobert/README.md`.
    *   Use `optimum`, `transformers`, and `pyvi` as dependencies.

3.  **Testing**:
    *   Add unit tests in `tests/unit/infrastructure/ai/test_phobert_onnx.py` to verify inference speed and correctness.

## Plan
1.  Update `.gitignore`.
2.  Create the download script.
3.  Update `Makefile`.
4.  Implement the wrapper class.
5.  Add tests.
