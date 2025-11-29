.PHONY: help install dev-install run-api run-queue run-scheduler setup-models setup-model setup-model-tiny setup-model-base setup-model-small setup-model-medium setup-model-large setup-whisper setup-whisper-custom setup-artifacts setup-artifacts-small setup-artifacts-medium docker-build docker-up docker-down docker-logs clean clean-old test test-library test-integration format lint upgrade

# ==============================================================================
# HELPERS
# ==============================================================================
help:
	@echo "Available commands (Managed by uv):"
	@echo ""
	@echo "📦 DEPENDENCIES:"
	@echo "  make install                 - Install dependencies (Sync environment)"
	@echo "  make dev-install             - Install all dependencies including dev tools"
	@echo "  make upgrade                 - Upgrade all packages in lock file"
	@echo ""
	@echo "🚀 RUN SERVICES:"
	@echo "  make run-api                 - Run API service locally"
	@echo "  make run-analytics-api       - Run Analytics Engine API (Phase 0)"
	@echo "  make run-analytics-consumer  - Run Analytics Engine consumer (Phase 0)"
	@echo ""
	@echo "🗄️  DATABASE (Phase 0):"
	@echo "  make db-init                 - Initialize Alembic"
	@echo "  make db-migrate              - Create new migration"
	@echo "  make db-upgrade              - Apply migrations"
	@echo "  make db-downgrade            - Rollback last migration"
	@echo ""
	@echo "🐳 DOCKER (Phase 0):"
	@echo "  make dev-up                  - Start development environment"
	@echo "  make dev-down                - Stop development environment"
	@echo "  make dev-logs                - View development logs"
	@echo ""
	@echo "🤖 PHOBERT ONNX:"
	@echo "  make download-phobert        - Download PhoBERT ONNX model from MinIO"
	@echo "  make test-phobert            - Run all PhoBERT tests"
	@echo "  make test-phobert-unit       - Run unit tests only"
	@echo "  make test-phobert-integration - Run integration tests (requires model)"
	@echo "  make test-phobert-performance - Run performance tests (requires model)"
	@echo ""
	@echo "🔍 SPACY-YAKE KEYWORD EXTRACTION:"
	@echo "  make download-spacy-model    - Download SpaCy model"
	@echo "  make test-spacyyake          - Run all SpaCy-YAKE tests"
	@echo "  make test-spacyyake-unit     - Run unit tests only"
	@echo "  make test-spacyyake-integration - Run integration tests (requires model)"
	@echo "  make test-spacyyake-performance - Run performance tests"
	@echo ""
	@echo "🧪 TESTING:"
	@echo "  make test                    - Run all tests"
	@echo ""
	@echo "🐳 DOCKER:"
	@echo "  make docker-build            - Build Docker images"
	@echo "  make docker-up               - Start all services"
	@echo "  make docker-down             - Stop all services"
	@echo "  make docker-logs             - View logs"
	@echo ""
	@echo "🧹 CLEANUP:"
	@echo "  make clean                   - Clean up compiled files and caches"
	@echo "  make clean-old               - Remove old/unused files"
	@echo ""
	@echo "✨ CODE QUALITY:"
	@echo "  make format                  - Format code (black)"
	@echo "  make lint                    - Lint code (flake8)"


# ==============================================================================
# DEPENDENCY MANAGEMENT (UV)
# ==============================================================================
# Cài đặt môi trường (mặc định uv sync cài cả dev deps, thêm --no-dev nếu chỉ muốn prod)
install:
	uv sync

# Nếu bạn chia group dev trong pyproject.toml, uv sync mặc định đã cài dev. 
# Target này giữ lại để tương thích thói quen cũ.
dev-install:
	uv sync

# Cập nhật các gói lên phiên bản mới nhất
upgrade:
	uv lock --upgrade

# Thêm thư viện mới (Ví dụ: make add pkg=requests)
add:
	uv add $(pkg)

# ==============================================================================
# RUN SERVICES
# ==============================================================================
# "uv run" tự động load .venv và environment, không cần trỏ đường dẫn python thủ công
# PYTHONPATH=. vẫn giữ để đảm bảo import các module gốc hoạt động đúng
run-api:
	PYTHONPATH=. uv run commands/api/main.py

run-api-refactored:
	PYTHONPATH=. uv run cmd/api/main.py

# Phase 0: Analytics Engine
run-analytics-api:
	PYTHONPATH=. uv run cmd/api/main.py

run-analytics-consumer:
	PYTHONPATH=. uv run commands/consumer/main.py

# ==============================================================================
# WHISPER SETUP
# ==============================================================================
# Download Whisper models from MinIO (for local development)
# Requires MinIO connection configured in .env
setup-models:
	@echo "Downloading Whisper models from MinIO..."
	PYTHONPATH=. uv run scripts/setup_models.py

# Download specific model (e.g., make setup-model MODEL=medium)
setup-model:
	@echo "Downloading model: $(MODEL)..."
	PYTHONPATH=. uv run scripts/setup_models.py $(MODEL)

# Quick shortcuts for common models
setup-model-tiny:
	@echo "Downloading tiny model..."
	PYTHONPATH=. uv run scripts/setup_models.py tiny

setup-model-base:
	@echo "Downloading base model..."
	PYTHONPATH=. uv run scripts/setup_models.py base

setup-model-small:
	@echo "Downloading small model..."
	PYTHONPATH=. uv run scripts/setup_models.py small

setup-model-medium:
	@echo "Downloading medium model..."
	PYTHONPATH=. uv run scripts/setup_models.py medium

setup-model-large:
	@echo "Downloading large model..."
	PYTHONPATH=. uv run scripts/setup_models.py large

# Build whisper.cpp binary from source (for local development)
# Requires: cmake, make, and whisper.cpp repo cloned
setup-whisper:
	@echo "Building whisper.cpp binary..."
	bash scripts/setup_whisper.sh

# Build whisper.cpp with specific models
setup-whisper-custom:
	@echo "Building whisper.cpp with models: $(MODELS)..."
	bash scripts/setup_whisper.sh --models "$(MODELS)"

# ==============================================================================
# WHISPER LIBRARY ARTIFACTS (Dynamic Model Loading)
# ==============================================================================
# Download Whisper library artifacts from MinIO
setup-artifacts:
	@echo "📦 Downloading Whisper library artifacts (default: small)..."
	PYTHONPATH=. uv run python scripts/download_whisper_artifacts.py small

setup-artifacts-small:
	@echo "📦 Downloading SMALL model artifacts..."
	PYTHONPATH=. uv run python scripts/download_whisper_artifacts.py small

setup-artifacts-medium:
	@echo "📦 Downloading MEDIUM model artifacts..."
	PYTHONPATH=. uv run python scripts/download_whisper_artifacts.py medium

# ==============================================================================
# AI MODELS (Phase 0.5)
# ==============================================================================
download-phobert:
	@echo "Downloading PhoBERT ONNX model..."
	@bash scripts/download_phobert_model.sh

test-phobert:
	@echo "Running PhoBERT tests..."
	@uv run pytest tests/phobert/ -v

test-phobert-unit:
	@echo "Running PhoBERT unit tests..."
	@uv run pytest tests/phobert/test_unit.py -v

test-phobert-integration:
	@echo "Running PhoBERT integration tests (requires model)..."
	@uv run pytest tests/phobert/test_integration.py -v

test-phobert-performance:
	@echo "Running PhoBERT performance tests (requires model)..."
	@uv run pytest tests/phobert/test_performance.py -v -m benchmark

# SpaCy-YAKE Keyword Extraction (Phase 0.6)
download-spacy-model:
	@echo "Downloading SpaCy model..."
	@uv run python -m spacy download en_core_web_sm

test-spacyyake:
	@echo "Running SpaCy-YAKE tests..."
	@uv run pytest tests/spacyyake/ -v

test-spacyyake-unit:
	@echo "Running SpaCy-YAKE unit tests..."
	@uv run pytest tests/spacyyake/test_unit.py tests/spacyyake/test_aspect_mapper.py -v

test-spacyyake-integration:
	@echo "Running SpaCy-YAKE integration tests (requires model)..."
	@uv run pytest tests/spacyyake/test_integration.py -v

test-spacyyake-performance:
	@echo "Running SpaCy-YAKE performance tests..."
	@uv run pytest tests/spacyyake/test_performance.py -v

# ==============================================================================
# DOCKER OPERATIONS
# ==============================================================================
docker-build:
	docker-compose build

docker-up:
	docker-compose up -d

docker-down:
	docker-compose down

docker-logs:
	docker-compose logs -f

docker-restart:
	docker-compose restart

docker-clean:
	docker-compose down -v

# Phase 0: Development Environment
dev-up:
	docker-compose -f docker-compose.dev.yml up -d

dev-down:
	docker-compose -f docker-compose.dev.yml down

dev-logs:
	docker-compose -f docker-compose.dev.yml logs -f

dev-clean:
	docker-compose -f docker-compose.dev.yml down -v

# ==============================================================================
# DATABASE OPERATIONS (Phase 0)
# ==============================================================================
db-init:
	PYTHONPATH=. uv run alembic init migrations

db-migrate:
	@read -p "Enter migration message: " msg; \
	PYTHONPATH=. uv run alembic revision --autogenerate -m "$$msg"

db-upgrade:
	PYTHONPATH=. uv run alembic upgrade head

db-downgrade:
	PYTHONPATH=. uv run alembic downgrade -1

db-reset:
	PYTHONPATH=. uv run alembic downgrade base
	PYTHONPATH=. uv run alembic upgrade head

# ==============================================================================
# CODE QUALITY & TESTING
# ==============================================================================
clean:
	@echo "🧹 Cleaning up compiled files and caches..."
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name "*.pyd" -delete
	rm -rf .pytest_cache
	rm -rf htmlcov
	rm -rf .coverage
	rm -rf dist
	rm -rf build
	rm -rf *.egg-info
	uv cache clean

clean-old:
	@echo "🧹 Removing old/unused files and directories..."
	@echo "Removing backup files..."
	find . -name "*.bak" -type f -delete
	find . -name "*~" -type f -delete
	@echo "Removing old __init__.py.bak files..."
	find . -name "__init__.py.bak" -type f -delete
	@echo "✅ Cleanup complete!"

test:
	@echo "🧪 Running all tests..."
	PYTHONPATH=. uv run pytest -v

test-library:
	@echo "🧪 Testing Whisper Library Adapter..."
	PYTHONPATH=. uv run pytest tests/test_whisper_library.py -v

test-integration:
	@echo "🧪 Testing Model Switching Integration..."
	PYTHONPATH=. uv run pytest tests/test_model_switching.py -v

test-small:
	@echo "🧪 Testing with SMALL model..."
	WHISPER_MODEL_SIZE=small PYTHONPATH=. uv run pytest tests/test_model_switching.py -v

test-medium:
	@echo "🧪 Testing with MEDIUM model..."
	WHISPER_MODEL_SIZE=medium PYTHONPATH=. uv run pytest tests/test_model_switching.py -v

format:
	uv run black core/ services/ commands/ adapters/ internal/ tests/

lint:
	uv run flake8 core/ services/ commands/ adapters/ internal/ tests/ --max-line-length=100

# ==============================================================================
# LOGS & SCALING
# ==============================================================================
scale-queue:
	docker-compose up -d --scale queue=3

logs-api:
	docker-compose logs -f api

logs-queue:
	docker-compose logs -f queue

logs-mongodb:
	docker-compose logs -f mongodb

logs-rabbitmq:
	docker-compose logs -f rabbitmq