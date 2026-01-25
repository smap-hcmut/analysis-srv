# ai_integration Specification

## Purpose
TBD - created by archiving change phobert_integration. Update Purpose after archive.
## Requirements
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

#### Scenario: K8s Deployment Model Loading

- **GIVEN** the Analytics Engine is deployed to Kubernetes
- **WHEN** the pod starts
- **THEN** PhoBERT model files SHALL be available at `/app/infrastructure/phobert/models/`
- **AND** SentimentAnalyzer SHALL initialize successfully with the loaded model

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

### Requirement: K8s Model Initialization

The system MUST automatically download and cache AI model artifacts when deployed to Kubernetes, ensuring models are available before the main application starts.

#### Scenario: InitContainer Downloads Model

- **GIVEN** a fresh Kubernetes pod deployment
- **WHEN** the pod starts
- **THEN** an initContainer SHALL download PhoBERT model from MinIO to a persistent volume
- **AND** the main container SHALL wait until model download completes
- **AND** the main container SHALL have access to the downloaded model files

#### Scenario: Model Caching with PVC

- **GIVEN** a PersistentVolumeClaim is bound to the pod
- **WHEN** the pod restarts
- **THEN** the initContainer SHALL skip download if model files already exist
- **AND** pod startup time SHALL be reduced on subsequent restarts

#### Scenario: MinIO Credentials Security

- **GIVEN** MinIO credentials are required for model download
- **WHEN** the initContainer runs
- **THEN** credentials SHALL be sourced from Kubernetes Secrets
- **AND** credentials SHALL NOT be baked into Docker images

