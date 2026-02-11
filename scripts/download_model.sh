#!/bin/bash
set -e

# PhoBERT Model Downloader for Docker
# Downloads model from MinIO to local directory

# Configuration from environment variables or defaults
MINIO_ENDPOINT="${MINIO_ENDPOINT:-localhost:9000}"
MINIO_ACCESS_KEY="${MINIO_ACCESS_KEY:-minioadmin}"
MINIO_SECRET_KEY="${MINIO_SECRET_KEY:-minioadmin}"
MINIO_BUCKET="${MINIO_BUCKET:-ml-models}"
MINIO_PREFIX="${MINIO_PREFIX:-phobert/phobert_sentiment}"
LOCAL_PATH="${LOCAL_PATH:-internal/model/phobert_sentiment}"

# Required files
REQUIRED_FILES=(
    "model.onnx"
    "config.json"
    "vocab.txt"
    "bpe.codes"
    "tokenizer_config.json"
)

echo "======================================================================"
echo "PhoBERT Model Downloader"
echo "======================================================================"
echo "MinIO Endpoint: $MINIO_ENDPOINT"
echo "Bucket: $MINIO_BUCKET"
echo "Remote Path: $MINIO_PREFIX"
echo "Local Path: $LOCAL_PATH"
echo "======================================================================"

# Check if model already exists
check_model_exists() {
    if [ ! -d "$LOCAL_PATH" ]; then
        return 1
    fi
    
    for file in "${REQUIRED_FILES[@]}"; do
        if [ ! -f "$LOCAL_PATH/$file" ]; then
            echo "Missing file: $file"
            return 1
        fi
    done
    
    return 0
}

# Check if model exists
if check_model_exists; then
    echo "Model already exists at $LOCAL_PATH"
    echo "Skipping download..."
    exit 0
fi

# Install mc (MinIO Client) if not exists
if ! command -v mc &> /dev/null; then
    echo "Installing MinIO Client (mc)..."
    
    # Detect OS
    OS=$(uname -s | tr '[:upper:]' '[:lower:]')
    ARCH=$(uname -m)
    
    case "$ARCH" in
        x86_64) ARCH="amd64" ;;
        aarch64|arm64) ARCH="arm64" ;;
    esac
    
    MC_URL="https://dl.min.io/client/mc/release/${OS}-${ARCH}/mc"
    
    curl -sSL "$MC_URL" -o /tmp/mc
    chmod +x /tmp/mc
    MC_BIN="/tmp/mc"
else
    MC_BIN="mc"
fi

# Configure MinIO alias
echo "Configuring MinIO connection..."
$MC_BIN alias set myminio "http://$MINIO_ENDPOINT" "$MINIO_ACCESS_KEY" "$MINIO_SECRET_KEY" --api S3v4

# Create local directory
mkdir -p "$LOCAL_PATH"

# Download each required file
echo "Downloading model files..."
for file in "${REQUIRED_FILES[@]}"; do
    remote_path="myminio/$MINIO_BUCKET/$MINIO_PREFIX/$file"
    local_file="$LOCAL_PATH/$file"
    
    echo "Downloading $file..."
    if ! $MC_BIN cp "$remote_path" "$local_file"; then
        echo "❌ Failed to download $file"
        exit 1
    fi
done

# Verify download
echo "Verifying download..."
if check_model_exists; then
    echo "======================================================================"
    echo "SUCCESS! Model downloaded to $LOCAL_PATH"
    echo "======================================================================"
    exit 0
else
    echo "======================================================================"
    echo "❌ FAILED! Model download incomplete"
    echo "======================================================================"
    exit 1
fi
