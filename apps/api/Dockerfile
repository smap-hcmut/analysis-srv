FROM registry.tantai.dev/smap/analysis-base:latest

RUN python -m pip install --no-cache-dir \
    "fastapi>=0.115.0" \
    "httpx>=0.28.0" \
    "uvicorn>=0.32.0"

COPY --chown=analytics:analytics apps/ apps/
COPY --chown=analytics:analytics config/ config/
COPY --chown=analytics:analytics internal/ internal/
COPY --chown=analytics:analytics pkg/ pkg/

USER analytics

CMD ["python", "-m", "apps.api.main"]
