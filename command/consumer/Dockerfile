# ==============================================================================
# Multi-stage Dockerfile for Analytics Consumer
# Build context: project root (.)
# ==============================================================================

# ==============================================================================
# Stage 1: Builder - Install dependencies and download models
# ==============================================================================
FROM python:3.12-slim AS builder

WORKDIR /build

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN pip install --no-cache-dir uv

# Copy dependency files (need README for build)
COPY pyproject.toml uv.lock README.md ./

# Install dependencies (Consumer with ML/Analytics libraries)
RUN uv pip install --system --no-cache -e .[consumer]

# Download SpaCy multilingual model (cached in builder layer)
RUN python -m spacy download xx_ent_wiki_sm

# ==============================================================================
# Stage 2: Runtime
# ==============================================================================
FROM python:3.12-slim

WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy Python packages from builder (includes SpaCy model)
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Create non-root user
RUN useradd -m -u 1000 analytics && \
    mkdir -p /app/logs /app/infrastructure/phobert/models && \
    chown -R analytics:analytics /app

# Copy application code
COPY --chown=analytics:analytics . .

# Switch to non-root user
USER analytics

# Run consumer
CMD ["python", "-m", "command.consumer.main"]
