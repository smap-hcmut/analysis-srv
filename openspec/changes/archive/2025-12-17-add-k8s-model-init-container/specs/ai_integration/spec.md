## ADDED Requirements

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

## MODIFIED Requirements

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
