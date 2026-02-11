.PHONY: help install sync run-consumer test lint format clean spacy-model spacy-list

# Default target
help:
	@echo "Available commands:"
	@echo "  make install       - Install dependencies"
	@echo "  make sync          - Sync dependencies with lock file"
	@echo "  make run-consumer  - Run consumer service"
	@echo "  make test          - Run tests"
	@echo "  make lint          - Run linters"
	@echo "  make format        - Format code"
	@echo "  make clean         - Clean cache and build files"
	@echo "  make spacy-model   - Download SpaCy model"
	@echo "  make spacy-list    - List installed SpaCy models"

# Install dependencies
install:
	uv sync

# Sync dependencies
sync:
	uv sync

# Run consumer service
run-consumer:
	uv run python -m apps.consumer.main

# Run tests (placeholder)
test:
	@echo "Running tests..."
	uv run pytest tests/ -v

# Lint code (placeholder)
lint:
	@echo "Running linters..."
	uv run ruff check .

# Format code (placeholder)
format:
	@echo "Formatting code..."
	uv run ruff format .

# Download SpaCy model
spacy-model:
	@echo "Downloading SpaCy multilingual model..."
	uv pip install https://github.com/explosion/spacy-models/releases/download/xx_ent_wiki_sm-3.7.0/xx_ent_wiki_sm-3.7.0-py3-none-any.whl

# List installed SpaCy models
spacy-list:
	@echo "Installed SpaCy models:"
	@uv run python -c "import spacy; print('\\n'.join(spacy.util.get_installed_models()))" 2>/dev/null || echo "No models installed"

# Clean cache and build files
clean:
	@echo "Cleaning cache and build files..."
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type f -name "*.pyo" -delete 2>/dev/null || true
	@echo "Clean complete!"

# Development setup
dev-setup: install
	@echo "Development environment setup complete!"
	@echo ""
	@echo "Optional: Download SpaCy model with 'make spacy-model'"
	@echo "Run 'make run-consumer' to start the consumer service"
