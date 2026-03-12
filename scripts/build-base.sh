#!/bin/bash

# ==============================================================================
# Analysis Base Image — Build and Push to Harbor Registry
#
# Builds the analysis-base image containing:
#   - All heavy Python deps (torch-cpu, transformers, optimum, spacy...)
#   - SpaCy xx_ent_wiki_sm model
#   - PhoBERT ONNX model (~515MB)
#
# Run this ONLY when:
#   - pyproject.toml / uv.lock changes
#   - PhoBERT model is updated
#
# Usage (from project root): ./scripts/build-base.sh [build-push|login|help]
# ==============================================================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
REGISTRY="${HARBOR_REGISTRY:-registry.tantai.dev}"
PROJECT="smap"
SERVICE="analysis-base"
DOCKERFILE="scripts/Dockerfile.base"
PLATFORM="${PLATFORM:-linux/amd64}"

# Harbor credentials (set HARBOR_USERNAME and HARBOR_PASSWORD in ~/.zshrc)
HARBOR_USER="${HARBOR_USERNAME:?HARBOR_USERNAME is not set. Export it in ~/.zshrc}"
HARBOR_PASS="${HARBOR_PASSWORD:?HARBOR_PASSWORD is not set. Export it in ~/.zshrc}"

# Helper functions
info()    { echo -e "${BLUE}[INFO]${NC} $1"; }
success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
error()   { echo -e "${RED}[ERROR]${NC} $1"; }

generate_tag() {
    date +"%y%m%d-%H%M%S"
}

get_image_name() {
    local tag="${1:-$(generate_tag)}"
    echo "${REGISTRY}/${PROJECT}/${SERVICE}:${tag}"
}

login() {
    info "Logging into Harbor registry: $REGISTRY"
    echo "$HARBOR_PASS" | docker login "$REGISTRY" -u "$HARBOR_USER" --password-stdin
    if [ $? -eq 0 ]; then
        success "Logged in successfully"
    else
        error "Login failed"
        exit 1
    fi
}

check_prerequisites() {
    if ! command -v docker &> /dev/null; then
        error "Docker is not installed"
        exit 1
    fi

    if ! docker buildx version &> /dev/null; then
        error "Docker buildx is not available"
        exit 1
    fi

    if [ ! -f "$DOCKERFILE" ]; then
        error "Dockerfile not found: $DOCKERFILE"
        error "Run this script from the project root directory"
        exit 1
    fi

    # Verify PhoBERT model exists
    if [ ! -f "internal/model/phobert/phobert.onnx" ]; then
        error "PhoBERT ONNX model not found: internal/model/phobert/phobert.onnx"
        error "Run download_model.sh first or ensure the model file exists"
        exit 1
    fi

    info "PhoBERT model found: $(du -sh internal/model/phobert/phobert.onnx | cut -f1)"
}

build_and_push() {
    check_prerequisites
    login

    local tag=$(generate_tag)
    local image_name=$(get_image_name "$tag")
    local image_latest=$(get_image_name "latest")

    info "Registry:   $REGISTRY"
    info "Image:      $image_name"
    info "Platform:   $PLATFORM"
    info "Dockerfile: $DOCKERFILE"
    warning "This build includes torch-cpu (~1.5GB) + PhoBERT (~515MB). Expect 10-20 mins on first build."
    echo ""

    docker buildx build \
        --platform "$PLATFORM" \
        --tag "$image_name" \
        --tag "$image_latest" \
        --file "$DOCKERFILE" \
        --progress=plain \
        --push \
        .

    if [ $? -eq 0 ]; then
        echo ""
        success "Base image built and pushed successfully!"
        info "Tagged:  $image_name"
        info "Latest:  $image_latest"
        echo ""
        info "Next step: run ./scripts/build-consumer.sh to rebuild the app image using this base."
    else
        error "Build and push failed"
        exit 1
    fi
}

show_help() {
    cat <<EOF
${GREEN}Analysis Base Image — Build and Push Script${NC}

Usage: $0 [command]

Commands:
    build-push    Build and push base image (default)
    login         Login to Harbor registry
    help          Show this help

Configuration:
    Registry:   $REGISTRY
    Project:    $PROJECT
    Service:    $SERVICE
    Platform:   $PLATFORM
    Dockerfile: $DOCKERFILE

Image Format:
    ${REGISTRY}/${PROJECT}/${SERVICE}:<YYMMDD-HHMMSS>
    ${REGISTRY}/${PROJECT}/${SERVICE}:latest

When to rebuild:
    - pyproject.toml or uv.lock changed (new/updated deps)
    - PhoBERT model updated (internal/model/phobert/)

EOF
}

case "${1:-build-push}" in
    build-push)
        build_and_push
        ;;
    login)
        login
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        error "Unknown command: $1"
        echo ""
        show_help
        exit 1
        ;;
esac
