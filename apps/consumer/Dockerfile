# ==============================================================================
# Analysis Consumer — App-only Dockerfile (fast builds)
#
# REQUIRES: registry.tantai.dev/smap/analysis-base:latest to exist.
# Run scripts/build-base.sh to build it if needed.
#
# This Dockerfile only adds application code on top of the base image,
# so kaniko builds via '!build analysis-consumer' complete in ~30 seconds.
#
# Rebuild base image (scripts/build-base.sh) ONLY when:
#   - pyproject.toml / uv.lock changes
#   - PhoBERT model updated
#
# Build:
#   docker build -f apps/consumer/Dockerfile -t analysis-consumer .
# ==============================================================================

FROM registry.tantai.dev/smap/analysis-base:latest

# Copy only application source code (no deps, no model — already in base)
COPY --chown=analytics:analytics apps/ apps/
COPY --chown=analytics:analytics config/ config/
COPY --chown=analytics:analytics internal/ internal/
COPY --chown=analytics:analytics pkg/ pkg/

USER analytics

CMD ["python", "-m", "apps.consumer.main"]
