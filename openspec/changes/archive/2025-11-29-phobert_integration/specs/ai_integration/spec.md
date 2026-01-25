# Spec: AI Integration

## ADDED Requirements

### Requirement: AI Model Management
The system MUST provide mechanisms to securely download and manage large AI model artifacts without committing them to version control.

#### Scenario: Download Model Artifacts
Given the developer needs the PhoBERT model
When they run `make download-phobert`
Then the script should prompt for MinIO credentials (IP, Access Key, Secret Key)
And download the model artifacts from the `phobert-onnx-artifacts` bucket to `infrastructure/phobert/models/`
And verify the presence of `model_quantized.onnx`.

#### Scenario: Git Ignore
Given the model artifacts are downloaded
When `git status` is run
Then the `infrastructure/phobert/models/` directory should be ignored.

### Requirement: PhoBERT Inference
The system MUST provide a high-performance inference wrapper for the PhoBERT ONNX model to predict sentiment from Vietnamese text.

#### Scenario: Sentiment Prediction
Given a Vietnamese text "Sản phẩm chất lượng cao"
When `PhoBERTONNX.predict` is called
Then it should return a dictionary with `rating` (4 or 5), `score` (confidence), and `sentiment` label.

#### Scenario: Performance
Given a standard input text
When inference is run
Then it should complete within 100ms (on standard CPU).
