.PHONY: help install dev-install upgrade run-api run-consumer dev-up dev-down dev-logs download-phobert download-spacy-model test test-phobert test-spacyyake clean format lint db-init db-migrate db-upgrade db-downgrade

# ==============================================================================
# HELPERS
# ==============================================================================
help:
	@echo "Available commands (Managed by uv):"
	@echo ""
	@echo "📦 DEPENDENCIES:"
	@echo "  make install                 - Install dependencies (Sync environment)"
	@echo "  make upgrade                 - Upgrade all packages in lock file"
	@echo ""
	@echo "🚀 RUN SERVICES:"
	@echo "  make run-api                 - Run API service locally"
	@echo "  make run-consumer            - Run Consumer service locally"
	@echo "  make run-example-preprocessing - Run Text Preprocessor example"
	@echo ""
	@echo "🐳 DEV ENVIRONMENT (Docker):"
	@echo "  make dev-up                  - Start dev services (Postgres, Redis, MinIO, RabbitMQ)"
	@echo "  make dev-down                - Stop dev services"
	@echo "  make dev-logs                - View dev services logs"
	@echo ""
	@echo "🤖 AI MODELS:"
	@echo "  make download-phobert        - Download PhoBERT ONNX model"
	@echo "  make download-spacy-model    - Download SpaCy model"
	@echo ""
	@echo "🧪 TESTING:"
	@echo "  make test                    - Run all tests"
	@echo "  make test-phobert            - Run PhoBERT tests"
	@echo "  make test-spacyyake          - Run SpaCy-YAKE tests"
	@echo "  make test-preprocessing      - Run Text Preprocessor tests"
	@echo ""
	@echo "🗄️  DATABASE:"
	@echo "  make db-init                 - Initialize Alembic"
	@echo "  make db-migrate              - Create new migration"
	@echo "  make db-upgrade              - Apply migrations"
	@echo "  make db-downgrade            - Rollback last migration"
	@echo ""
	@echo "✨ CODE QUALITY:"
	@echo "  make format                  - Format code (black)"
	@echo "  make lint                    - Lint code (flake8)"
	@echo "  make clean                   - Clean up cache files"

# ==============================================================================
# DEPENDENCY MANAGEMENT
# ==============================================================================
install:
	uv sync

dev-install:
	uv sync

upgrade:
	uv lock --upgrade

# ==============================================================================
# RUN SERVICES
# ==============================================================================
run-api:
	PYTHONPATH=. uv run commands/api/main.py

run-consumer:
	PYTHONPATH=. uv run commands/consumer/main.py

run-example-preprocessing:
	@echo "Running Text Preprocessor example..."
	@PYTHONPATH=. uv run examples/preprocess_example.py

# ==============================================================================
# DEV ENVIRONMENT
# ==============================================================================
dev-up:
	docker-compose -f docker-compose.dev.yml up -d

dev-down:
	docker-compose -f docker-compose.dev.yml down

dev-logs:
	docker-compose -f docker-compose.dev.yml logs -f

# ==============================================================================
# AI MODELS
# ==============================================================================
download-phobert:
	@echo "Downloading PhoBERT ONNX model..."
	@bash scripts/download_phobert_model.sh

download-spacy-model:
	@echo "Downloading SpaCy model..."
	@uv run python -m spacy download en_core_web_sm

# ==============================================================================
# TESTING
# ==============================================================================
test:
	@echo "🧪 Running all tests..."
	PYTHONPATH=. uv run pytest -v

test-phobert:
	@echo "Running PhoBERT tests..."
	@uv run pytest tests/phobert/ -v

test-spacyyake:
	@echo "Running SpaCy-YAKE tests..."
	@uv run pytest tests/spacyyake/ -v

test-preprocessing:
	@echo "Running Text Preprocessor tests..."
	@uv run pytest tests/preprocessing/ -v

test-preprocessing-unit:
	@echo "Running Text Preprocessor unit tests..."
	@uv run pytest tests/preprocessing/test_unit.py -v

test-preprocessing-integration:
	@echo "Running Text Preprocessor integration tests..."
	@uv run pytest tests/preprocessing/test_integration.py -v

test-preprocessing-performance:
	@echo "Running Text Preprocessor performance tests..."
	@uv run pytest tests/preprocessing/test_performance.py -v

# ==============================================================================
# DATABASE
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

# ==============================================================================
# CODE QUALITY
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

format:
	uv run black core/ infrastructure/ commands/ internal/ tests/

lint:
	uv run flake8 core/ infrastructure/ commands/ internal/ tests/ --max-line-length=100