# ==============================================================================
# Multi-stage Dockerfile for Analytics Consumer (Optimized)
# Build context: project root (.)
#
# Optimizations applied:
#   - Uses official uv image (pre-installed, faster than pip install uv)
#   - CPU-only PyTorch (~200MB vs ~2GB with CUDA)
#   - Selective COPY (only needed dirs, not COPY . .)
#   - .dockerignore excludes model.safetensors (~515MB), docs, scripts
#   - Minimal /usr/local/bin copy (no entire bin dir)
#   - Better layer caching (deps before source)
#   - Non-root user, PYTHONUNBUFFERED, PYTHONDONTWRITEBYTECODE
#
# Build:
#   docker build -f apps/consumer/Dockerfile -t analysis-consumer .
# ==============================================================================

# ------------------------------------------------------------------------------
# Stage 1: Builder - Install dependencies & download models
# ------------------------------------------------------------------------------
FROM ghcr.io/astral-sh/uv:0.6-python3.12-bookworm-slim AS builder

WORKDIR /build

# Install build dependencies for native extensions (greenlet, snappy, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libsnappy-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency files first (better layer caching)
COPY pyproject.toml uv.lock README.md ./

# Create minimal package stubs so hatchling can build the project metadata
RUN mkdir -p apps pkg config internal && \
    touch apps/__init__.py pkg/__init__.py config/__init__.py internal/__init__.py

# Install CPU-only PyTorch first (saves ~1.5GB vs full CUDA build)
RUN uv pip install --system --no-cache \
    torch --index-url https://download.pytorch.org/whl/cpu

# Install all project dependencies (torch already satisfied, won't be replaced)
RUN uv pip install --system --no-cache .

# Download SpaCy multilingual model
RUN python -m spacy download xx_ent_wiki_sm

# ------------------------------------------------------------------------------
# Stage 2: Runtime - Minimal production image
# ------------------------------------------------------------------------------
FROM python:3.12-slim-bookworm

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Create non-root user
RUN groupadd -g 1000 analytics && \
    useradd -m -u 1000 -g analytics analytics && \
    mkdir -p /app/logs && \
    chown -R analytics:analytics /app

# Copy only Python site-packages from builder (not entire /usr/local/bin)
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages

# Copy only necessary application code (selective, not COPY . .)
COPY --chown=analytics:analytics apps/ apps/
COPY --chown=analytics:analytics config/ config/
COPY --chown=analytics:analytics internal/ internal/
COPY --chown=analytics:analytics pkg/ pkg/

USER analytics

CMD ["python", "-m", "apps.consumer.main"]
