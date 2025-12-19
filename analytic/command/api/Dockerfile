FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

# Copy dependency files
COPY pyproject.toml uv.lock README.md ./

# Install dependencies system-wide (no venv) - API only
RUN uv pip install --system --no-cache -e .[api]

# Copy source code
COPY . .

# Create non-root user first
RUN groupadd -r analytics && \
    useradd -r -g analytics -d /home/analytics -m analytics

# Create logs directory with proper permissions (writable by analytics user)
RUN mkdir -p /app/logs && \
    chown -R analytics:analytics /app /home/analytics && \
    chmod 777 /app/logs

USER analytics

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Command to run the API service - use system Python directly
CMD ["python", "-m", "command.api.main"]