# Project Context

## Purpose
Analytics Engine - A high-performance analytics processing service for social media content analysis, featuring Vietnamese sentiment analysis using PhoBERT ONNX.

## Tech Stack

- **Language**: Python 3.12+
- **Package Manager**: `uv` (faster than Poetry)
- **Web Framework**: FastAPI (planned)
- **Database**: PostgreSQL with Alembic migrations
- **Cache**: Redis (planned)
- **Message Queue**: RabbitMQ (planned)
- **Object Storage**: MinIO (for model artifacts)
- **AI/ML**:
  - PhoBERT ONNX - Vietnamese sentiment analysis (5-class)
  - SpaCy + YAKE - Keyword extraction (English, extensible)
  - PyVi - Vietnamese text segmentation
  - ONNX Runtime - Optimized model inference, Docker Compose
- **Storage**: MinIO (for model artifacts)

## Project Conventions

### Code Style
- **Python**: Follow PEP 8, use Black for formatting (line length: 100)
- **Type Hints**: Required for all function signatures
- **Imports**: Use `# type: ignore` for third-party packages without stubs
- **Naming**: 
  - Classes: PascalCase
  - Functions/variables: snake_case
  - Constants: UPPER_SNAKE_CASE (in `constants.py`)

### Architecture Patterns
- **Clean Architecture**: Separation of concerns with layers:
  - `commands/`: Entry points (application layer)
  - `internal/`: Implementation details
  - `core/`: Shared functionality
  - `services/`: Business logic
  - `infrastructure/`: External integrations (AI, database)
- **Dependency Injection**: Use DI container pattern
- **Interface-based Design**: Define interfaces for external dependencies

### Testing Strategy
- **Unit Tests**: Mock external dependencies, test business logic
- **Integration Tests**: Test with real models (skipped if not downloaded)
- **Performance Tests**: Benchmark critical paths
- **Test Organization**: Mirror source structure in `tests/`
- **Coverage Goal**: Aim for 80%+ coverage on core logic

### Git Workflow
- **Branching**: Feature branches from `main`
- **Commits**: Conventional commits format
- **OpenSpec**: Use OpenSpec for major changes (proposal → implementation → archive)

## Domain Context
- **Vietnamese NLP**: PhoBERT model for 5-class sentiment analysis (1-5 stars)
- **Model Management**: ONNX quantized models stored in MinIO, downloaded on-demand
- **Performance**: Target <100ms inference time for sentiment analysis

## Important Constraints
- **Model Size**: Keep model artifacts out of git (use `.gitignore`)
- **Memory**: Optimize for CPU inference (no GPU required)
- **Dependencies**: Use `uv` for fast, reproducible dependency management
- **Python Version**: Minimum 3.10, recommended 3.12+

## External Dependencies

- **MinIO**: Model artifact storage (PhoBERT ONNX models, SpaCy models)
- **PostgreSQL**: Primary database
- **Redis**: Caching layer (planned)
- **RabbitMQ**: Message queue (planned)
- **SpaCy**: NLP library for keyword extraction
- **YAKE**: Statistical keyword extractionel (fine-tuned for sentiment)
- **PyVi**: Vietnamese text segmentation library
- **ONNX Runtime**: Optimized inference engine
