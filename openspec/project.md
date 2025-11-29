# Project Context

## Purpose
Analytics Engine - A high-performance analytics processing service for social media content analysis, featuring Vietnamese sentiment analysis using PhoBERT ONNX.

## Tech Stack
- **Backend**: Python 3.12+, FastAPI, SQLAlchemy
- **Database**: PostgreSQL (with Alembic migrations)
- **AI/ML**: PhoBERT ONNX (Vietnamese sentiment analysis)
- **Package Manager**: uv
- **Containerization**: Docker, Docker Compose
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
- **MinIO**: Self-hosted object storage for model artifacts
- **PhoBERT**: Pre-trained Vietnamese BERT model (fine-tuned for sentiment)
- **PyVi**: Vietnamese text segmentation library
- **ONNX Runtime**: Optimized inference engine
